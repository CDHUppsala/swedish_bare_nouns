import sys, os, argparse, tarfile
from xml.etree.ElementTree import iterparse

def us(s):
    return s if s and s != "" else "_"

def to_conllu(sent_elem, fd=sys.stdout):
    sent_id = sent_elem.attrib.get('id', '_')
    print(f"# sent_id = {sent_id}", file=fd)
    for token in sent_elem.iter('token'):
        id = token.attrib.get('ref', '_')
        form = token.text if token.text else "_"
        raw_lemma = token.attrib.get('lemma', '_') or '_'
        lemma = us(raw_lemma.strip("|"))
        upos = "_"
        xpos = token.attrib.get('pos', '_') or '_'
        raw_feats = token.attrib.get('ufeats', '_') or '_'
        feats = us(raw_feats.strip("|"))
        head = token.get('dephead', "0") or "0"
        deprel = token.attrib.get('deprel', '_') or '_'
        deps = "_"
        misc = "_"
        print(f"{id}\t{form}\t{lemma}\t{upos}\t{xpos}\t{feats}\t{head}\t{deprel}\t{deps}\t{misc}", file=fd)
    print("", file=fd)

class Stop(Exception):
    pass

def process_xml(xml_path, output_dir, sentence_by_file=None, max_files=None):
    """
    Process an XML file and convert it to CoNLL-U.
    If sentence_by_file is None (default), the entire XML is converted into a single CoNLL-U file (<base_name>.conllu).
    If sentence_by_file is an integer, splits into <base_name>_0001.conllu, etc.
    """
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    sent_cpt = 0
    file_cpt = 0

    if sentence_by_file is None:
        output_file_path = os.path.join(output_dir, f"{base_name}.conllu")
        total_sents = 0
        try:
            with open(output_file_path, "w", encoding="utf-8") as out_fd:
                for _, elem in iterparse(xml_path, events=("end",)):
                    if elem.tag == "sentence":
                        to_conllu(elem, out_fd)
                        total_sents += 1
                        elem.clear()
            print(f"Converted {xml_path} -> {output_file_path} ({total_sents} sentences)")
        except Exception as e:
            print(f"Error processing {xml_path}: {e}")
        return

    # Optional split mode if sentence_by_file is explicitly set
    current_file = None
    def get_or_create_file():
        nonlocal file_cpt, current_file
        if current_file is None or current_file.closed:
            file_cpt += 1
            if max_files and file_cpt > max_files:
                raise Stop
            file_name = os.path.join(output_dir, f"{base_name}_{file_cpt:04d}.conllu")
            current_file = open(file_name, "w", encoding="utf-8")
        return current_file

    try:
        for _, elem in iterparse(xml_path, events=("end",)):
            if elem.tag == "sentence":
                target_file = get_or_create_file()
                to_conllu(elem, target_file)
                sent_cpt += 1
                if sent_cpt >= sentence_by_file:
                    target_file.close()
                    sent_cpt = 0
                elem.clear()
        if current_file and not current_file.closed:
            current_file.close()
        print(f"Converted {xml_path} into {file_cpt} chunks in {output_dir}")
    except Stop:
        if current_file and not current_file.closed:
            current_file.close()
    except Exception as e:
        print(f"Error processing {xml_path}: {e}")

def create_tar(output_dir, tar_name="results.tar.gz"):
    with tarfile.open(tar_name, "w:gz") as tar:
        tar.add(output_dir, arcname=os.path.basename(output_dir))
    return tar_name

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract sentences from XML to CoNLL-U")
    parser.add_argument("xml_files", nargs="+", help="XML files to process")
    parser.add_argument("--output_dir", default="data", help="Output directory (default: data)")
    parser.add_argument("--split", type=int, default=None, help="Optional: Number of sentences per file if further splitting is desired")
    parser.add_argument("--max_files", type=int, default=None, help="Optional: Maximum number of split files to create per XML")
    parser.add_argument("--archive", default=None, help="Optional: Name of the resulting tar archive (e.g. results.tar.gz)")
    
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    
    for xml_file in args.xml_files:
        if os.path.exists(xml_file):
            print(f"Processing {xml_file}...")
            process_xml(xml_file, args.output_dir, sentence_by_file=args.split, max_files=args.max_files)
        else:
            print(f"File not found: {xml_file}")
    
    if args.archive:
        archive_path = create_tar(args.output_dir, args.archive)
        print(f"Results collected in {archive_path}")