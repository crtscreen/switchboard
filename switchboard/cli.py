import argparse

def main():
    parser = argparse.ArgumentParser(description="Switchboard SSH chat")
    parser.add_argument("--data", default="data", help="Private server data directory")
    parser.parse_args()
    print("testing")