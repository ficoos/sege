#! /usr/bin/env python
import argparse
import sys

import segeCompiler

def generate(fname, options):

    target = segeCompiler.compileSource(fname)
    with open(options.output, "wb") as f:
        target.write_to_png(f)
    target.finish()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sequence Diagram Compiler.')
    parser.add_argument('file', metavar='FILE', type=str,
                           help='file to compile')

    parser.add_argument('--output', dest="output", metavar='OUT',
                           help='Output file name', action='store',
                           default="res.png")

    options = parser.parse_args(sys.argv[1:])
    generate(options.file, options)
