import numpy as np
import pyaudio
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

from mibis_xor import MiBiSXOR


class SimpleTRNG:
    def __init__(self, use_dual_mixers=True):
        self.sample_rate = 44100
        self.chunk_size = 1024  # 1024 samples per read, 1024 * 2 = 2KB per read
        self.pyaudio_instance = None
        self.stream = None
        self.mibis_processor = MiBiSXOR(use_dual_mixers=use_dual_mixers)

    def __enter__(self):
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            info = self.pyaudio_instance.get_host_api_info_by_index(0)

            # Find first available input device
            device_id = None
            for i in range(info.get('deviceCount')):
                device_info = self.pyaudio_instance.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels') > 0:
                    device_id = i
                    break

            if device_id is None:
                raise RuntimeError("Microphone not working")

            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.chunk_size
            )

        except Exception:
            self.stream = None

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

    def generate_random_bits(self, num_bits):
        """Generate random bits using MiBiS&XOR post-processing"""
        if self.stream is None:
            raise RuntimeError("ERROR: microphone error")
        try:
            # Calculate needed raw bits (MiBiS&XOR compression ~50%)
            raw_bits_needed = max(num_bits * 3, 2048)
            duration = (raw_bits_needed / self.sample_rate)
            chunks_needed = int(self.sample_rate * duration / self.chunk_size)

            # Collect audio data
            audio_data = []
            for i in range(chunks_needed):
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    chunk = np.frombuffer(data, dtype=np.int16)
                    audio_data.extend(chunk)
                except Exception:
                    continue

            # Extract raw bits from audio
            raw_bits = self._extract_bits_from_audio(audio_data)

            # Process through MiBiS&XOR
            processed_bits = self.mibis_processor.process_bits(raw_bits, max_bits=len(raw_bits))

            return processed_bits[:num_bits]

        except Exception:
            raise RuntimeError("ERROR1")

    def _extract_bits_from_audio(self, audio_samples):
        """Extract bits from audio samples using multiple bit positions"""
        if not audio_samples:
            return np.array([], dtype=np.uint8)  # Return empty if no samples

        samples = np.array(audio_samples, dtype=np.int16)
        bits = []

        for sample in samples:
            # Extract multiple bits for better entropy
            bits.append(sample & 1)  # LSB
            bits.append((sample >> 1) & 1)  # Bit 1
            bits.append((sample >> 3) & 1)  # Bit 3
            bits.append((sample >> 7) & 1)  # Bit 7

        return np.array(bits, dtype=np.uint8)


class DigitalSignature:
    """Digital signature class using TRNG with MiBiS&XOR entropy"""

    def __init__(self, trng):
        self.trng = trng

    def generate_rsa_keys(self, key_size=256):
        total_bytes_used = 0

        def my_random_func(n):
            nonlocal total_bytes_used
            # print(f"RSA needs {n} bytes...")

            # Generate exactly as many bits as needed by RSA
            bits_needed = n * 8
            random_bits = self.trng.generate_random_bits(bits_needed)
            random_bits = np.array(random_bits, dtype=np.uint8)

            # Ensure multiple of 8 bits
            if len(random_bits) % 8 != 0:
                padding = 8 - (len(random_bits) % 8)
                random_bits = np.append(random_bits, np.zeros(padding, dtype=np.uint8))

            # Convert to bytes
            random_bytes = []
            for i in range(0, len(random_bits), 8):
                byte_bits = random_bits[i:i + 8]
                byte_value = 0
                for j, bit in enumerate(byte_bits):
                    byte_value += bit * (2 ** (7 - j))
                random_bytes.append(byte_value)

            result = bytes(random_bytes[:n])  # Return exactly n bytes
            total_bytes_used += n
            return result

        print("Generating RSA key using TRNG...")
        key = RSA.generate(key_size, randfunc=my_random_func)
        print(f"Total {total_bytes_used} bytes gathered from microphone")
        return key

    def read_file(self, file_path):
        """Read file content as bytes"""
        try:
            with open(file_path, 'rb') as file:
                return file.read()
        except Exception as e:
            raise Exception("File read error")

    def sign_file(self, file_path, private_key):
        """Sign file with private key"""
        file_content = self.read_file(file_path)
        hash_obj = SHA256.new(file_content)
        signature = pkcs1_15.new(private_key).sign(hash_obj)
        return signature

    def verify_file_signature(self, file_path, signature, public_key):
        """Verify file signature"""
        try:
            file_content = self.read_file(file_path)
            hash_obj = SHA256.new(file_content)
            pkcs1_15.new(public_key).verify(hash_obj, signature)
            return True
        except Exception:
            return False

def test():
    """Check if changing file content invalidates the signature"""
    print("\nTEST 1: integrity")
    print("=" * 40)

    # Create test files
    test_file1 = "original.txt"
    test_file2 = "not_original.txt"

    with SimpleTRNG(use_dual_mixers=True) as trng:
        ds = DigitalSignature(trng)
        user1_key = ds.generate_rsa_keys(1024)

        # Sign original message
        signature = ds.sign_file(test_file1, user1_key)

        # Verify original file - should be True
        result1 = ds.verify_file_signature(test_file1, signature, user1_key.publickey())

        # Verify second file - should be False
        result2 = ds.verify_file_signature(test_file2, signature, user1_key.publickey())

        print(f"original: {'PASS' if result1 else 'FAIL'}")
        print(f"second file: {'FAIL (correct)' if not result2 else 'PASS (error!)'}")

    """Check if a signature created with one private key can be verified with a different public key"""
    print("\nTEST 2: non-repudiation")
    print("=" * 40)

    with SimpleTRNG(use_dual_mixers=True) as trng:
        ds = DigitalSignature(trng)

        # Generate second key
        user2_key = ds.generate_rsa_keys(1024)

        # user1 signs the file
        signature = ds.sign_file(test_file1, user1_key)

        # Test verification with different keys
        result3 = ds.verify_file_signature(test_file1, signature, user1_key.publickey())
        result4 = ds.verify_file_signature(test_file1, signature, user2_key.publickey())

        print(f"user1_key key: {'PASS' if result3 else 'FAIL'}")
        print(f"user2_key key: {'FAIL (correct)' if not result4 else 'PASS (error!)'}")

        return result1, result2, result3, result4


def main():
    print("Digital signature with TRNG")
    print("Press Enter to start (microphone will begin recording)...")
    input()

    try:
        # Run tests
        result1, result2, result3, result4 = test()

        if result1 and not result2:
            print("\nintegrity test - OK")
        else:
            print("\nintegrity test - FAIL")

        if result3 and not result4:
            print("\nnon-repudiation test - OK")
        else:
            print("\nnon-repudiation test - FAIL")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
