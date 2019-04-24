#!/isr/bin/env python
# coding=utf-8
# wujian@17.10.24

import wave
import numpy as np
import matplotlib.pyplot as plt
# import utils

MAX_INT16 = np.iinfo(np.int16).max

def get_fft_size(num_samples):
    fft_size = 1
    while fft_size < num_samples:
        fft_size = fft_size * 2
    return int(fft_size)

def get_frame_info(frame_rate, window_size, frame_offset):
    """
        Returns frame_size and frame_offset, given the paramters:
            frame_rate:     sample rate of original wave
            window_size:    time length of each frame(ms)
            frame_offset:   time offset of each frame(ms)
    """
    samples_per_ms = frame_rate / 1000
    frame_size  = int(window_size * samples_per_ms)
    offset_size = int(frame_offset * samples_per_ms)
    return frame_size, offset_size

def pre_emphase(signal, filter_coeff=0.97):
    for index in range(1, signal.size):
        signal[index] -= filter_coeff * signal[index - 1]
    signal[0] -= filter_coeff * signal[0]
    return signal

def compute_spectrum(wave_wrapper, transpose=False, window_type='hamming'):
    """
        Compute the DFT of each frames in the wrapper:
        1. default apply hamming-window on each frame
        2. calculate the real-fft results of each frame
        NOTE:   real-fft returns a complex vector of size N + 1, 
                N equals half of frame_size, egs: T x W => T x (W / 2 + 1)    
    """
    frames = wave_wrapper.subframes()
    num_frames, frame_size = frames.shape
    assert window_type in ['hamming', 'hanning']
    window = np.hamming(frame_size) if window_type == 'hamming' \
            else np.hanning(frame_size)
    fft_size = get_fft_size(frame_size)
    # print('fft_size is %d' % fft_size)
    # print('num_frames is %d' % num_frames)
    spectrum = np.zeros([num_frames, int(fft_size / 2 + 1)], dtype=np.complex)
    # padding zeros
    feature_in = np.zeros(fft_size)
    for index in range(num_frames):
        feature_in[: frame_size] = frames[index] * window 
        spectrum[index] = np.fft.rfft(feature_in)
    return spectrum if not transpose else np.transpose(spectrum)

def plot_spectrum(spectrum, frame_duration, title="samples.wav"):
    """
        Visilize the spectrum, now only adds time info along
        x-axis without frequency info along y-axis
    """
    num_frames, num_bins = spectrum.shape
    log_spectrum = np.zeros([num_frames, num_bins])
    for index in range(num_frames):
        log_spectrum[index] = np.log(np.abs(spectrum[index]))
    plt.imshow(np.transpose(log_spectrum), origin="lower", \
            cmap = "jet", aspect = "auto", interpolation = "none")
    xlocs = np.linspace(0, num_frames - 1, 5)
    plt.yticks([])
    plt.title(title)
    plt.xticks(xlocs, ["%.02f" % l for l in (xlocs * frame_duration)])
    plt.xlabel("time (s)")
    plt.show()

def plot_mask(mask, frame_duration, title="samples.wav"):
    """
        Visilize the spectrum, now only adds time info along
        x-axis without frequency info along y-axis
    """
    num_frames, num_bins = mask.shape
    plt.imshow(np.transpose(mask), origin="lower", \
            cmap ="jet", aspect="auto", interpolation="none")
    xlocs = np.linspace(0, num_frames - 1, 5)
    plt.yticks([])
    plt.title(title)
    plt.xticks(xlocs, ["%.02f" % l for l in (xlocs * frame_duration)])
    plt.xlabel("time (s)")
    plt.show()

def write_wave(samples, frame_rate, dest):
    """
        Dumps wave samples to a file, with default config:
        1 channel, 2 bit per sample
    """
    dest_wave = wave.open(dest, "wb")
    # 1 channel; int16 default
    dest_wave.setparams((1, 2, frame_rate, samples.size, 'NONE', 'not compressed'))
    dest_wave.writeframes(samples.astype(np.int16).tostring())
    print("1 channels; 2 bytes per sample; {num_samples} samples; " \
            "{frame_rate} samples per sec. OUT[{path}]".format(path=dest, \
            num_samples=samples.size, frame_rate=frame_rate))
    dest_wave.close()

def reconstruct_wave(spectrum, dest, frame_rate=16000, window_size=25, 
                    frame_offset=10, filter_coeff=0.97):
    """
        Reconstruct wave samples from the spectrum, using overlapadd and post-filter
        The spectrum is obtained by rfft, so apply irfft to restore the orignal signal.
    """
    num_frames, num_bins = spectrum.shape
    frame_size, offset_size = get_frame_info(frame_rate, window_size, frame_offset)
    num_samples = int((num_frames - 1) * offset_size + frame_size)
    window = np.hamming(frame_size)
    samples = np.zeros(num_samples)
    for index in range(num_frames):
        base = index * offset_size
        frame = np.fft.irfft(spectrum[index])
        samples[base: base + frame_size] += frame[: frame_size] * window
    # filter
    for index in range(1, num_frames):
        samples[index] += filter_coeff * samples[index - 1]
    # write_wave(samples, frame_rate, dest)
    samples /= samples.max()
    write_wave(samples * MAX_INT16, frame_rate, dest)


class WaveWrapper(object):
    """
        A wrapper for a single wave file, maintaining some basic infomation
    """
    def __init__(self, path, window_size=25, frame_offset=10):
        src_wave = wave.open(path, "rb")
        self.wave_path = path
        self.num_channels, self.sample_bits, self.frame_rate, \
            self.num_samples, _, _ = src_wave.getparams()
        self.byte_data   = src_wave.readframes(self.num_samples)
        self.frame_size, self.offset_size = get_frame_info(self.frame_rate, window_size, frame_offset)
        self.num_frames  = int((self.num_samples - self.frame_size) / self.offset_size + 1)
        self.frame_duration = 1 / self.frame_rate * self.offset_size
        src_wave.close() 
    
    def subframes(self, normalize=True):
        """
            Convert the samples to several frames
        """
        assert self.sample_bits == 2
        samples = np.fromstring(self.byte_data, dtype=np.int16)
        frames  = np.zeros([self.num_frames, self.frame_size])
        for index in range(self.num_frames):
            base = index * self.offset_size
            frames[index] = samples[base: base + self.frame_size]
        return frames if not normalize else frames / MAX_INT16

    def __str__(self):
        return "{num_channels} channels; {sample_bits} bytes per sample; " \
            "{num_samples} samples; {frame_rate} samples per sec. IN[{path}]".format(path=self.wave_path, \
            num_channels=self.num_channels, sample_bits=self.sample_bits, \
            num_samples=self.num_samples, frame_rate=self.frame_rate)

def check_status(data_list):
    shape = None
    for matrix in data_list:
        if not shape:
            shape = matrix.shape
        else:
            assert shape == matrix.shape, "Matrix shape need to be same in the list"
    return shape

class MultiChannelWrapper(object):
    """
        Wrapper to handle multiple channels/wave
    """
    def __init__(self, script):
        with open(script, "r") as scp:
            scp_list = [line.strip() for line in scp if line.strip]
        self.wrappers = [WaveWrapper(path) for path in scp_list]
    
    def subframes(self, normalize=True):
        frames = [wrapper.subframes(normalize) for wrapper in self.wrappers]
        shape_per_item = check_status(frames)
        return shape_per_item, frames
    
    def spectrums(self, transpose=False):
        spects = [compute_spectrum(wrapper, transpose) for wrapper in self.wrappers]
        shape_per_item = check_status(spects)
        return shape_per_item, spects
    
    def __str__(self):
        return '\n'.join([str(wrapper) for wrapper in self.wrappers])

