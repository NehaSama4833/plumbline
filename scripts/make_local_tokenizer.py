"""Build a tiny local Hugging Face tokenizer directory (no network needed).

GuideLLM wants a tokenizer to build synthetic prompts. This sandbox cannot reach the Hugging Face
Hub, so we point GuideLLM's `model=` at a local directory made by this script. Run it with the
Python of the environment where GuideLLM (and thus transformers/tokenizers) is installed:

    python scripts/make_local_tokenizer.py /path/to/localtok
"""

import os
import sys

from tokenizers import Tokenizer, models, pre_tokenizers, trainers
from transformers import PreTrainedTokenizerFast

out = sys.argv[1] if len(sys.argv) > 1 else "localtok"
words = ("the quick brown fox jumps over lazy dog and runs through green fields under blue sky "
         "while birds sing songs of morning light").split()
tok = Tokenizer(models.WordLevel(unk_token="<unk>"))
tok.pre_tokenizer = pre_tokenizers.Whitespace()
tok.train_from_iterator([" ".join(words)] * 50,
                        trainers.WordLevelTrainer(special_tokens=["<unk>", "<s>", "</s>"]))
os.makedirs(out, exist_ok=True)
PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="<unk>", bos_token="<s>",
                        eos_token="</s>").save_pretrained(out)
print("wrote", out)
