"""Generate demo results from bundled fictional text only.

Usage: python scripts/build_evidence_review.py /path/to/model-directory
The directory must contain the pinned model's config.json and tokenizer.json,
plus its quantized ONNX weights named model.onnx.
"""
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'cross-encoder/nli-deberta-v3-xsmall'
REVISION = 'a150876415327c80daeff35ca6f68f5ed8cf5c24'
LABELS = {
    'contradiction': 'possible_conflict',
    'entailment': 'consistent',
    'neutral': 'insufficient_evidence',
}


def build(model_dir):
    fixture = ROOT / 'fixtures' / 'evidence-review.json'
    pairs = json.loads(fixture.read_text())
    config = json.loads((model_dir / 'config.json').read_text())
    tokenizer = Tokenizer.from_file(str(model_dir / 'tokenizer.json'))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    model = ort.InferenceSession(str(model_dir / 'model.onnx'), sess_options=options,
                                 providers=['CPUExecutionProvider'])
    for pair in pairs:
        first, second = [source['text'] for source in pair['sources']]
        encoding = tokenizer.encode(first, second)
        inputs = {'input_ids': encoding.ids, 'attention_mask': encoding.attention_mask,
                  'token_type_ids': encoding.type_ids}
        output = model.run(None, {i.name: np.array([inputs[i.name]], dtype=np.int64)
                                  for i in model.get_inputs()})[0][0]
        pair['finding'] = LABELS[config['id2label'][str(int(output.argmax()))].lower()]
    return {'model': MODEL, 'revision': REVISION, 'mode': 'offline_fixture_inference', 'comparisons': pairs}


if __name__ == '__main__':
    result = build(Path(sys.argv[1]))
    output = ROOT / 'fixtures' / 'evidence-review-results.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
