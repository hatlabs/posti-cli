"""Tests for shipment operations."""

import base64
import json
import os
from unittest.mock import patch, MagicMock

from posti_cli.core.client_v2 import PostiV2Client
from posti_cli.core.oauth import OAuthToken
from posti_cli.core.shipments import create_shipment, save_pdfs


def _make_client():
    oauth = MagicMock(spec=OAuthToken)
    oauth.access_token = "test-bearer-token"
    return PostiV2Client(url="https://api.example.com", oauth=oauth)


def _mock_response(data):
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestCreateShipment:
    def test_posts_to_v2_endpoint_with_bearer_auth(self):
        client = _make_client()
        data = {"shipment": {"parcels": [{"weight": 1.0}]}}

        with patch("urllib.request.urlopen", return_value=_mock_response([{}])) as mock:
            create_shipment(client, data)
            req = mock.call_args[0][0]
            assert "/v2/shipping/order" in req.full_url
            assert "returnFile=true" in req.full_url
            assert req.get_header("Authorization") == "Bearer test-bearer-token"

    def test_defaults_value_per_parcel_to_false(self):
        client = _make_client()
        data = {
            "shipment": {
                "parcels": [
                    {"weight": 2.5, "contents": "Electronics"},
                ]
            }
        }

        with patch("urllib.request.urlopen", return_value=_mock_response([{}])) as mock:
            create_shipment(client, data)
            req = mock.call_args[0][0]
            sent_data = json.loads(req.data)
            assert sent_data["shipment"]["parcels"][0]["valuePerParcel"] is False

    def test_preserves_explicit_value_per_parcel(self):
        client = _make_client()
        data = {
            "shipment": {
                "parcels": [
                    {"weight": 2.5, "valuePerParcel": True},
                ]
            }
        }

        with patch("urllib.request.urlopen", return_value=_mock_response([{}])) as mock:
            create_shipment(client, data)
            req = mock.call_args[0][0]
            sent_data = json.loads(req.data)
            assert sent_data["shipment"]["parcels"][0]["valuePerParcel"] is True

    def test_handles_data_without_shipment_key(self):
        client = _make_client()
        data = {"printConfig": {"target1Media": "thermo-225"}}

        with patch("urllib.request.urlopen", return_value=_mock_response([{}])):
            create_shipment(client, data)


class TestSavePdfs:
    def test_saves_v2_prints_format(self, tmp_path):
        pdf_content = b"%PDF-test-content"
        response = [{
            "parcels": [{"parcelNo": "JJFI123"}],
            "prints": [{
                "data": base64.b64encode(pdf_content).decode(),
                "pdf_type": "ADDRESSLABEL",
            }],
        }]

        saved = save_pdfs(response, str(tmp_path))
        assert len(saved) == 1
        assert saved[0].endswith("JJFI123_ADDRESSLABEL.pdf")
        assert open(saved[0], "rb").read() == pdf_content

    def test_saves_v1_pdfs_format(self, tmp_path):
        pdf_content = b"%PDF-v1-content"
        response = [{
            "parcels": [{"parcelNo": "JJFI456"}],
            "pdfs": [{
                "pdf": base64.b64encode(pdf_content).decode(),
                "pdf_type": "ADDRESSLABEL",
            }],
        }]

        saved = save_pdfs(response, str(tmp_path))
        assert len(saved) == 1
        assert saved[0].endswith("JJFI456_ADDRESSLABEL.pdf")
        assert open(saved[0], "rb").read() == pdf_content

    def test_prefers_v2_prints_over_v1_pdfs(self, tmp_path):
        """When both prints and pdfs are present, uses prints."""
        v2_content = b"%PDF-v2"
        response = [{
            "parcels": [{"parcelNo": "JJFI789"}],
            "prints": [{
                "data": base64.b64encode(v2_content).decode(),
                "pdf_type": "ADDRESSLABEL",
            }],
            "pdfs": [{
                "pdf": base64.b64encode(b"%PDF-v1").decode(),
                "pdf_type": "ADDRESSLABEL",
            }],
        }]

        saved = save_pdfs(response, str(tmp_path))
        assert len(saved) == 1
        assert open(saved[0], "rb").read() == v2_content

    def test_handles_empty_response(self, tmp_path):
        saved = save_pdfs([], str(tmp_path))
        assert saved == []
