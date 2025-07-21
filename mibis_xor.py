import numpy as np
import math
import logging
from threading import Event, Thread
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MiBiSXOR:
    def __init__(self, use_dual_mixers=True):
        """
        Initializes the MiBiSXOR processor for mixing and XORing bits.

        Args:
            use_dual_mixers (bool): Whether to use two alternating mixers (recommended)
        """
        self.use_dual_mixers = use_dual_mixers
        self.output_buffer = []
        self.stop_event = Event()
        logger.info(f"Initializing MiBiSXOR, mode: {'dual mixers' if use_dual_mixers else 'single mixer'}")

    def process_bits(self, input_bits, max_bits=None):
        """
        Processes bits using the MiBiS&XOR algorithm.

        Args:
            input_bits (numpy.ndarray): Array of input bits
            max_bits (int, optional): Maximum number of bits to process

        Returns:
            numpy.ndarray: Array of processed random bits
        """
        if max_bits is not None and max_bits < len(input_bits):
            input_bits = input_bits[:max_bits]

        if self.use_dual_mixers:
            return self._process_with_dual_mixers(input_bits)
        else:
            return self._process_with_single_mixer(input_bits)

    def _process_with_single_mixer(self, input_bits):
        """
        Processes bits using a single mixer.

        Args:
            input_bits (numpy.ndarray): Array of input bits

        Returns:
            numpy.ndarray: Array of processed random bits
        """
        logger.info("Processing with single mixer")
        start_time = time.time()

        num_bits = len(input_bits)
        steps = self._calculate_mixing_steps(num_bits)

        mixed_bits = self._mix_bits(input_bits, steps)
        output_bits = self._xor_adjacent_bits(mixed_bits)

        elapsed_time = time.time() - start_time
        logger.info(f"Processed {len(input_bits)} bits into {len(output_bits)} random bits in {elapsed_time:.3f}s")

        return np.array(output_bits, dtype=np.uint8)

    def _process_with_dual_mixers(self, input_bits):
        """
        Processes bits using two alternating mixers.

        Args:
            input_bits (numpy.ndarray): Array of input bits

        Returns:
            numpy.ndarray: Array of processed random bits
        """
        start_time = time.time()

        midpoint = len(input_bits) // 2
        bits1 = input_bits[:midpoint]
        bits2 = input_bits[midpoint:]

        steps1 = self._calculate_mixing_steps(len(bits1))
        steps2 = self._calculate_mixing_steps(len(bits2))

        mixed1 = self._mix_bits(bits1, steps1)
        mixed2 = self._mix_bits(bits2, steps2)

        output1 = self._xor_adjacent_bits(mixed1)
        output2 = self._xor_adjacent_bits(mixed2)

        output_bits = output1 + output2

        elapsed_time = time.time() - start_time
        return np.array(output_bits, dtype=np.uint8)

    def _calculate_mixing_steps(self, num_bits):
        """
        Calculates the optimal number of mixing steps for the given number of bits.

        Based on the formula from the paper: n = log2(yn - 1) + 1, where yn is the number of bits.

        Args:
            num_bits (int): Number of input bits

        Returns:
            int: Number of mixing steps
        """
        if num_bits <= 1:
            return 1
        return math.floor(math.log2(num_bits - 1) + 1)

    def _mix_bits(self, input_bits, steps):
        """
        Mixes bits according to the MiBiS algorithm from the paper.

        Args:
            input_bits (numpy.ndarray): Array of input bits
            steps (int): Number of mixing steps

        Returns:
            list: List of mixed bits
        """
        buffer_size = 2 ** (steps - 1) + 1
        mixed_buffer = [0] * buffer_size

        # Insert the first two bits at the start and end of the buffer
        if len(input_bits) > 0:
            mixed_buffer[0] = input_bits[0]
        if len(input_bits) > 1:
            mixed_buffer[-1] = input_bits[1]

        input_idx = 2
        occupied_positions = [0, buffer_size - 1]

        for step in range(2, steps + 1):
            new_positions = []

            for i in range(len(occupied_positions) - 1):
                left_pos = occupied_positions[i]
                right_pos = occupied_positions[i + 1]
                middle_pos = (left_pos + right_pos) // 2

                if input_idx < len(input_bits) and mixed_buffer[middle_pos] == 0:
                    mixed_buffer[middle_pos] = input_bits[input_idx]
                    input_idx += 1
                    new_positions.append(middle_pos)

            occupied_positions.extend(new_positions)
            occupied_positions.sort()

            if input_idx >= len(input_bits):
                break

        return mixed_buffer

    def _xor_adjacent_bits(self, mixed_bits):
        """
        Performs XOR operation on adjacent bits.

        Args:
            mixed_bits (list): List of mixed bits

        Returns:
            list: List of XOR results
        """
        result = []
        for i in range(0, len(mixed_bits) - 1, 2):  # step by two
            result.append(mixed_bits[i] ^ mixed_bits[i+1])
        return result

    def start_continuous_processing(self, input_callback, output_callback, block_size=1024):
        """
        Starts continuous background bit processing.

        Args:
            input_callback: Function providing blocks of input bits
            output_callback: Function handling blocks of output bits
            block_size: Number of bits per processing block
        """
        logger.info(f"Starting continuous processing, block size: {block_size}")
        self.stop_event.clear()

        thread = Thread(target=self._continuous_processing_worker,
                        args=(input_callback, output_callback, block_size))
        thread.daemon = True
        thread.start()
        return thread

    def _continuous_processing_worker(self, input_callback, output_callback, block_size):
        """
        Worker function for continuous processing.

        Args:
            input_callback: Function providing input bit blocks
            output_callback: Function handling output bit blocks
            block_size: Size of bit blocks to process
        """
        mixer1_buffer = []
        mixer2_buffer = []
        active_mixer = 1  # Which mixer is active

        while not self.stop_event.is_set():
            new_bits = input_callback(block_size)

            if new_bits is None or len(new_bits) == 0:
                time.sleep(0.01)  # Small pause if no new bits
                continue

            if active_mixer == 1:
                mixer1_buffer.extend(new_bits)

                if len(mixer1_buffer) >= block_size:
                    active_mixer = 2
                    processed_bits = self._process_with_single_mixer(np.array(mixer1_buffer))
                    mixer1_buffer = []
                    output_callback(processed_bits)
            else:
                mixer2_buffer.extend(new_bits)

                if len(mixer2_buffer) >= block_size:
                    active_mixer = 1
                    processed_bits = self._process_with_single_mixer(np.array(mixer2_buffer))
                    mixer2_buffer = []
                    output_callback(processed_bits)

    def stop_continuous_processing(self):
        """Stops continuous processing."""
        logger.info("Stopping continuous processing")
        self.stop_event.set()
