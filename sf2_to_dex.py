#!/usr/bin/env python
"""
cleanup and refactor -> pretty much a rewrite

soundfonts are messy, you gotta kind of figure out where the note names
and velocities are in sample name. usually the pitch info is wack
"""

from chunk import Chunk
import logging
import os
import re
import struct
import wave

logging.basicConfig(level=logging.INFO)

SAMPLE_TYPES = {1: 'mono', 2: 'right', 4: 'left', 8: 'linked'}
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
ENHARMONICS = {
    'Db': 'C#',
    'Eb': 'D#',
    'Gb': 'F#',
    'Ab': 'G#',
    'Bb': 'A#',
}


def _read_dword(f):
    return struct.unpack('<i', f.read(4))[0]


def _read_word(f):
    return struct.unpack('<h', f.read(2))[0]


def _read_byte(f):
    return struct.unpack('<b', f.read(1))[0]


def _write_dword(f, v):
    f.write(struct.pack('<i', v))


def _write_word(f, v):
    f.write(struct.pack('<h', v))


class SfSample:
    def __init__(self):
        pass

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'SfSample(name="{}",start={})'.format(self.name, self.start)


def parse_sf2(sf2file):
    samples = []
    with open(sf2file, 'rb') as f:
        chfile = Chunk(f)
        _ = chfile.getname()  # riff
        _ = chfile.read(4)    # WAVE
        while 1:
            try:
                chunk = Chunk(chfile, bigendian=0)
            except EOFError:
                break
            name = chunk.getname()
            if name == 'smpl':
                sample_data_start = chfile.tell() + 8
                logging.debug('samples start: {}'.format(sample_data_start))
                chunk.skip()
            elif name == 'shdr':
                for i in range((chunk.chunksize / 46) - 1):
                    s = SfSample()
                    s.name = chfile.read(20).rstrip('\0')
                    s.start = _read_dword(chfile)
                    s.end = _read_dword(chfile)
                    s.startLoop = _read_dword(chfile)
                    s.endLoop = _read_dword(chfile)
                    s.sampleRate = _read_dword(chfile)
                    s.pitch = _read_byte(chfile)
                    s.correction = _read_byte(chfile)
                    s.link = _read_word(chfile)
                    s.type = _read_word(chfile)
                    samples.append(s)
                chfile.read(46)
            elif name == 'LIST':
                _ = chfile.read(4)
            else:
                chunk.skip()
    for s in samples:
        type_name = SAMPLE_TYPES[s.type & 0x7fff]
        logging.debug('{} {} {} {} {} {} {} {} {} {}'.format(
            s.name,
            type_name,
            s.pitch,
            s.start,
            s.end,
            s.startLoop,
            s.endLoop,
            s.sampleRate,
            s.correction,
            s.link
        ))
    return samples, sample_data_start


def write_loop(filename):
    with open(filename, 'r+b') as f:
        f.seek(4)
        riff_size = _read_dword(f)
        f.seek(4)
        _write_dword(f, riff_size + 0x76)
        f.seek(8 + riff_size)
        _write_dword(f, 0x20657563)        # 'cue '
        _write_dword(f, 0x34)
        _write_dword(f, 0x2)                # num cues
        _write_dword(f, 0x1)                # id
        _write_dword(f, s.startLoop-s.start)        # position
        _write_dword(f, 0x61746164)        # 'data'
        _write_dword(f, 0x0)
        _write_dword(f, 0x0)
        _write_dword(f, s.startLoop-s.start)        # position
        _write_dword(f, 0x2)                # id
        _write_dword(f, s.endLoop-s.start)        # position
        _write_dword(f, 0x61746164)        # 'data'
        _write_dword(f, 0x0)
        _write_dword(f, 0x0)
        _write_dword(f, s.endLoop-s.start)        # position
        _write_dword(f, 0x5453494C)        # 'LIST'
        _write_dword(f, 0x32)
        _write_dword(f, 0x6C746461)        # 'adtl'
        _write_dword(f, 0x6C62616C)        # 'labl'
        _write_dword(f, 0x10)
        _write_dword(f, 0x1)                # id
        _write_dword(f, 0x706F6F4C)        # 'Loop'
        _write_dword(f, 0x61745320)        # ' Sta'
        _write_dword(f, 0x7472)            # 'rt'
        _write_dword(f, 0x6C62616C)        # 'labl'
        _write_dword(f, 0x0E)
        _write_dword(f, 0x2)                # id
        _write_dword(f, 0x706F6F4C)        # 'Loop'
        _write_dword(f, 0x646E4520)        # ' End'
        _write_word(f, 0x0)
        f.close()


if __name__ == '__main__':
    import sys

    sf2file = sys.argv[1]

    samples, sample_data_start = parse_sf2(sf2file)

    F = open(sf2file, 'rb')
    F2 = open(sf2file, 'rb')

    # make a dir for our samples
    folder_name = os.path.basename(sf2file).split('.')[0]
    folder_name = "".join(x for x in folder_name if x.isalnum() or x == ' ')
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
    os.chdir(folder_name)

    for i, s in enumerate(samples):
        # Here's where we gotta get creative, depending on the soundfont
        type_name = SAMPLE_TYPES[s.type & 0x7fff]

        # mono or L, we'll pick up R channel via s.link
        if s.type not in [1, 4]:
            # print 'skipping', type_name, s.name
            continue

        # os impl
        """
        filename = "".join(x for x in s.name if x.isalnum())
        filename += '_'
        filename += note_names[s.pitch % 12]
        filename += str((s.pitch/12) - 1)
        filename += '.wav'
        """

        # Steinway B-JNv2.0.sf2
        """
        n, note, end = re.split('([ABCDEFG]#?[0123456789])', s.name)
        filename = '{}_{}.wav'.format(s.name.strip().replace(' ', ''), note)
        """

        # Chateau Grand-v1.8.sf2
        """
        pre, note, end = re.split('([ABCDEFG]#?[0123456789])', s.name)
        vel_match = re.findall('([01234567])L', end)
        if not vel_match:
            continue
        filename = 'Chateau_{}_V{}.wav'.format(note, vel_match[0])
        """

        # Rhodes EPs Plus-JN1.5.sf2
        """
        if not s.name.startswith('RHODES'):
            continue
        pre, note, end = re.split('([ABCDEFG]#?[0123456789])', s.name)
        filename = '{}_{}_V{}.wav'.format(s.name.replace(' ', '-'), note, end.strip())
        filename = 'RHODES_{}_V{}.wav'.format(note, end.strip())
        """

        # Nice-Steinway-v3.8.sf2
        """
        pre, note, end = re.split('([ABCDEFG][#b]?[0123456789])', s.name)
        note, lvl = note[:-1], note[-1]
        note = ENHARMONICS.get(note, note)
        filename = 'Piano.ff.{}_V{}.wav'.format(note, lvl)
        """

        print '[{}]\t-> [{}]'.format(s.name, filename)
        continue

        # once we're ok with filenames, write a file
        g = wave.open(filename, 'w')
        g.setsampwidth(2)
        g.setframerate(s.sampleRate)
        F.seek(sample_data_start + 2*s.start)
        frames = s.end-s.start+1
        if s.type == 1:
            g.setnchannels(1)
            data = F.read(2*frames)
            g.writeframesraw(data)
        else:
            g.setnchannels(2)
            F2.seek(sample_data_start + 2 * samples[s.link].start)
            for i in range(frames):
                data = F.read(2)
                g.writeframesraw(data)
                data = F2.read(2)
                g.writeframesraw(data)
        g.close()
        loop_length = s.endLoop - s.startLoop
        if loop_length > 1:
            write_loop(filename)
