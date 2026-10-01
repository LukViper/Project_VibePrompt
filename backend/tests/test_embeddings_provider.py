from app.nlp.embeddings import embedding_metadata, get_embedder


def test_fallback_clearly_identified():
    meta = embedding_metadata()
    assert "provider" in meta
    assert "dimension" in meta
    if meta["provider"] == "LexicalFallback":
        assert meta["is_lexical_fallback"] is True
    else:
        assert meta["is_lexical_fallback"] is False


def test_embedder_encode_runs():
    vectors = get_embedder().encode(["hello world"])
    assert vectors.shape[0] == 1
