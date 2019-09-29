# python cmd_key.py --action encode --input-file privatekey-firestore.json --output-file privatekey-firestore.json.b64 
# python cmd_key.py --action encode --input-file privatekey.json --output-file privatekey.json.b64 

import argparse
from base64io import Base64IO

def encode_key(source_file, encoded_file):
    with open(source_file, "rb") as source, open(encoded_file, "wb") as target:
        with Base64IO(target) as encoded_target:
            for line in source:
                encoded_target.write(line)

def decode_key(encoded_file, target_file):
    with open(encoded_file, "rb") as encoded_source, open(target_file, "wb") as target:
        with Base64IO(encoded_source) as source:
            for line in source:
                target.write(line)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', dest='action', help='encode or decode')
    parser.add_argument('--input-file', dest='input_file', help='input file path')
    parser.add_argument('--output-file', dest='output_file', help='output file path')
    args = parser.parse_args()

    if not args.action or not args.input_file or not args.output_file:
        print(parser.print_help())
    
    print(args.action)
    print(args.input_file)
    print(args.output_file)

    if args.action == 'encode':
        encode_key(args.input_file, args.output_file)

    if args.action == 'decode':
        decode_key(args.input_file, args.output_file)
