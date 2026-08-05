from packer.engine.common.config_schema import TinyDecoderCfg, compose_config


def test_pack_plugin_names_default():
    c = TinyDecoderCfg()
    assert c.arch == "tiny-decoder"
    assert c.tokenizer == "byte-bpe"
    assert c.decode == "teacher-forced-greedy"
    assert c.codec == "delta-varint-v1"
    assert c.weight_decay == 0.0
    assert c.seed == 0


def test_pack_fields_compose_and_override():
    cfg = compose_config(overrides=["engine.pack.seed=7", "engine.pack.codec=delta-varint-v1"])
    assert cfg.engine.pack.seed == 7
    assert cfg.engine.pack.arch == "tiny-decoder"


def test_research_fixed_profile_is_complete_and_non_degenerate():
    cfg = compose_config(overrides=["engine/pack=research_fixed"])
    pack = cfg.engine.pack

    assert pack.arch == "tiny-decoder"
    assert pack.tokenizer == "byte-fixed"
    assert pack.vocab_size == 257
    assert pack.context_len == 1024
    assert pack.min_sequence_tokens == 256
    assert pack.max_serialized_bytes_per_token == 1.0
