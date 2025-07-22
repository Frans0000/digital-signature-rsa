# Digital Signature with On-Demand TRNG (MiBiS\&XOR)

This project demonstrates how to generate and verify **digital signatures** using RSA keys whose randomness is derived entirely from a **True Random Number Generator (TRNG)** based on microphone input and **MiBiS\&XOR** post-processing.

The TRNG component is based on the method from:

> **S. Nikolić, M. Veinović**,
> *"Advancement of True Random Number Generators Based on Sound Cards Through Utilization of a New Post-processing Method"*,
> Wireless Personal Communications, vol. 91, pp. 603–622, 2016.

Randomness is gathered **on demand**, only when needed for cryptographic operations.

---

## What This Project Does

* Generates **RSA key pairs** from true random bits captured from microphone audio.
* Uses those keys to **digitally sign** any file.
* Verifies the signature using the corresponding public key.
* Includes tests for **integrity** and **non-repudiation** of digital signatures.

The purpose is to show how external entropy can be used for cryptographic signing.

---

## Why MiBiS\&XOR?

The TRNG uses raw bits extracted from microphone noise and post-processes them using the **MiBiS\&XOR** method to improve entropy quality.

MiBiS\&XOR performs multiple interleaved bit insertions followed by XOR operations. This produces high-quality random bits suitable for cryptographic key material.

> In this project, the TRNG is not the goal — it's simply a trusted entropy source used **on demand** for key generation.

---

## Digital Signature Workflow

1. **Key Generation**: Random bits from TRNG are passed into RSA key generation.
2. **Signing**: A file is hashed and signed using the generated private key.
3. **Verification**: The signature is validated using the corresponding public key.

This mirrors real-world usage of asymmetric cryptography but adds an extra level of unpredictability by using external analog randomness.

---

RSA key generation in this project is tightly integrated with a custom TRNG. When calling `RSA.generate(key_size, randfunc=...)`, the library internally requests a specific number of random bytes multiple times, depending on the size of the key being generated. For each such request `n`, our `my_random_func(n)` converts it to `n * 8` bits and uses the microphone-based TRNG to generate exactly that many bits. These bits are grouped into bytes and returned to RSA. Mathematically, the RSA algorithm needs to generate two large random primes `p` and `q`, each roughly `key_size/2` bits long, so the total entropy required scales with the key size. For example, a 1024-bit RSA key requires generating primes of ~512 bits, and thus multiple calls to `randfunc(n)` with byte sizes adding up to around that scale. The use of real entropy ensures stronger key unpredictability compared to traditional pseudorandom number generators.

RSA is an asymmetric cryptographic algorithm that uses a key pair: a public key and a private key. The public key can be shared with anyone and is used to encrypt messages or verify digital signatures, while the private key is kept secret and is used to decrypt messages or create signatures.

---

## How to Run

You will be prompted to press Enter. The microphone will begin capturing audio to collect entropy, and the program will:

* Generate RSA keys
* Sign a file
* Verify signature against two files
* Run integrity and non-repudiation tests

---

## Tests Included

### 1. Integrity

Confirms that any modification of a signed file causes signature verification to fail.

### 2. Non-repudiation

Checks that a signature cannot be validated using a public key that does not match the signing private key.

---

## Reference

Nikolić, S., & Veinović, M. (2016).
*Advancement of True Random Number Generators Based on Sound Cards Through Utilization of a New Post-processing Method*.
Wireless Personal Communications, **91**, 603–622.

---
