import json

from ai_template_python.data_foundation.document_generation import generate_synthetic_documents
from ai_template_python.data_foundation.synthetic import generate_synthetic_dataset


def test_generated_documents_have_synthetic_provenance_and_manifest(tmp_path) -> None:
    count = generate_synthetic_documents(generate_synthetic_dataset(), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert count == len(manifest) == 18
    assert {document["document_type"] for document in manifest} == {
        "contract",
        "policy",
        "supplier_profile",
    }
    assert all(document["is_synthetic"] for document in manifest)
    assert all((tmp_path / document["path"]).exists() for document in manifest)
    assert "SYNTHETIC PORTFOLIO DATA" in (tmp_path / "contract-s102.md").read_text(encoding="utf-8")
