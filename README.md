# PKCS11 Codelab using Python GAPIC grpc client libraries.

This is a codelab that demonstrates the sample use case of using Python GAPIC grpc client libraries with mTLS authentication where the certificate is loaded with PKCS11 interface. This codelab uses [Python Cloud KMS client library](https://github.com/googleapis/python-kms) as an example. The transport is grpc.

## 1. Pre-requisite

- This codelab is supposed to be ran at Debian GNU/Linux.
- Your environment should have Python 3 installed.

## 2. Set up openssl, pkcs11 and SoftHSM

### 2.1 Install openssl with pkcs11
First install openssl with its [PKCS11 engine](https://github.com/OpenSC/libp11#openssl-engines).

```bash
# add to /etc/apt/sources.list
  deb http://http.us.debian.org/debian/ testing non-free contrib main

# then
$ export DEBIAN_FRONTEND=noninteractive 
$ apt-get update && apt-get install libtpm2-pkcs11-1 tpm2-tools libengine-pkcs11-openssl opensc -y
```

### 2.2 Install SoftHSM.

SoftHSM is as the name suggests, a sofware "HSM" module used for testing. It is of course not hardware backed but the module does allow for a PKCS11 interface which we will also use for testing.
- [SoftHSM Install](https://www.opendnssec.org/softhsm/)

### 2.3 Configure openssl.

Set the pkcs11 provider and module directly into openssl (make sure `libpkcs11.so` engine reference and `libsofthsm2.so` exist first!)

- edit `/etc/ssl/openssl.cnf` as follows
```bash
openssl_conf = openssl_def
[openssl_def]
engines = engine_section

[engine_section]
pkcs11 = pkcs11_section

[pkcs11_section]
engine_id = pkcs11
dynamic_path = /usr/lib/x86_64-linux-gnu/engines-1.1/libpkcs11.so
MODULE_PATH = /usr/local/lib/softhsm/libsofthsm2.so
```

```bash
$ ls /usr/lib/x86_64-linux-gnu/engines-1.1/
afalg.so  libpkcs11.so  padlock.so  pkcs11.la  pkcs11.so

$ ls /usr/local/lib/softhsm/
libsofthsm2.a  libsofthsm2.la  libsofthsm2.so

$ openssl engine
  (rdrand) Intel RDRAND engine
  (dynamic) Dynamic engine loading support
  (pkcs11) pkcs11 engine

$ openssl engine -t -c pkcs11
  (pkcs11) pkcs11 engine
  [RSA, rsaEncryption, id-ecPublicKey]
      [ available ]
```

## 3. Download the codelab and its dependencies

### 3.1 Create a working directory and a Python virtual environment.
```bash
# Create a working directory.
$ mkdir my_directory
$ cd my_directory

# Create and activate a Python virtual environment
$ pyenv virtualenv my_env
$ pyenv local my_env
```

### 3.2 Download grpc and install a custom build
```bash
# Download the grpc repo.
$ git clone https://github.com/grpc/grpc.git

# Install a custom build with system openssl
$ cd grpc/
$ git submodule update --init
$ GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 python -m pip install .
$ cd ..
```

### 3.3 Download the codelab repo

```bash
$ git clone https://github.com/arithmetic1728/python-grpc-mtls-codelab.git
$ cd python-grpc-mtls-codelab.git

# Install the dependencies.
$ python -m pip install -r requirements.txt
```

## 4. Save mTLS cert and key into SoftHSM

### 4.1 Generate mTLS cert and key

```bash
$ /opt/google/endpoint-verification/bin/apihelper --print_certificate
```

This command will print out the following:
```
-----BEGIN CERTIFICATE-----
<omitted>
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
<omitted>
-----END PRIVATE KEY-----
```

Copy the top certificate part into a cert.pem file, and the bottom key part into a key.pem file. Then convert
the pem files into der files with openssl.

```bash
$ openssl ec -inform PEM -outform DER -in key.pem -out key.der
$ openssl x509 -inform PEM -outform DER -in cert.pem -out cert.der
```

### 4.2 Initialize SoftHSM

First create a `tokens` folder.
```bash
$ mkdir tokens
```

Then open the `softhsm.conf` file in the current folder, and set the `directories.tokendir` value to the absolute path of the
`tokens` folder. This way SoftHSM will save tokens into the `./tokens/` folder.

```bash
# softhsm.conf content looks like this
log.level = DEBUG
objectstore.backend = file
directories.tokendir = /absolute/path/of/tokens/folder/
slots.removable = true
```

Next initialize SoftHSM with [pkcs11-too](https://manpages.debian.org/testing/opensc/pkcs11-tool.1.en.html).

```bash
export SOFTHSM2_CONF=./softhsm.conf

## init softhsm
pkcs11-tool --module /usr/local/lib/softhsm/libsofthsm2.so --slot-index=0 --init-token --label="token1" --so-pin="123456"

## Change pin
pkcs11-tool --module /usr/local/lib/softhsm/libsofthsm2.so  --label="token1" --init-pin --so-pin "123456" --pin mynewpin
```

### 4.3 Write cert and key into SoftHSM

Here we use `1111` as the key id and `mtlskey` as the label for both the cert and the key.

```bash
# Import the private key into SoftHSM
$ pkcs11-tool  --module /usr/local/lib/softhsm/libsofthsm2.so --pin mynewpin \
   --write-object key.der --type privkey --id 1111 --label mtlskey --slot-index 0

# Import the cert into SoftHSM
$ pkcs11-tool  --module /usr/local/lib/softhsm/libsofthsm2.so --pin mynewpin \
   --write-object cert.der --type cert --id 1111 --label mtlskey --slot-index 0

# List the objects in SoftHSM, make sure we have both the key and the cert.
$ pkcs11-tool --module /usr/local/lib/softhsm/libsofthsm2.so  --list-objects --pin mynewpin
    Using slot 0 with a present token (0x828d64)
Using slot 0 with a present token (0x39a7340d)
Certificate Object; type = X.509 cert
  label:      mtlskey
  subject:    DN: CN=Google Endpoint Verification
  ID:         1111
Private Key Object; EC
  label:      mtlskey
  ID:         1111
  Usage:      decrypt, sign, unwrap
  Access:     sensitive
```

## 5. Run the sample application

### 5.1 Set up application default credentials

First we need to set the credentials by logging in with `sijunliu@beyondcorp.us` account.
```bash
$ gcloud auth application-default login
```

This command generates a `~/.config/gcloud/application_default_credentials.json` file. Add 
`"quota_project_id": "sijunliu-dca-test",` to the json file if the file doesn't contain it.

Next set the environment variable to enable mTLS in google auth library.
```bash
$ export GOOGLE_API_USE_CLIENT_CERTIFICATE=true
```

### 5.2 Run the sample with raw cert and key bytes

Edit `sample_raw_key.py`, fill in the cert and key bytes, then run it.

You should see:
```bash
$ python sample_raw_key.py 
ListKeyRingsPager<>
```

### 5.3 Run the sample with raw cert bytes, and the key from SoftHSM

Edit `sample_hsm_key.py`, fill in the cert bytes. The key will have `engine:<engine_id>:<key_id>` format.
Since our engine id is `pkcs11` and the key id is `1111`, so the key we use is `engine:pkcs11:1111`. 

Run the `sample_hsm_key.py` sample, it will prompt a message asking for the PIN, just type mynewpin.
You should see:
```bash
$ python sample_hsm_key.py 
Enter PKCS#11 token PIN for token1:
ListKeyRingsPager<>
```

Note: in order to load the private key from SoftHSM, both the key and cert or public key must be written
to SoftHSM.