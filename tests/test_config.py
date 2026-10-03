import os
import json
import pytest
from pathlib import Path
from main import parse_owner_ids, load_config


def test_parse_owner_ids():
    # None
    assert parse_owner_ids(None) == set()
    # Empty string
    assert parse_owner_ids("") == set()
    # Single int
    assert parse_owner_ids(12345) == {12345}
    # List of ints/strings
    assert parse_owner_ids([123, "456", 789]) == {123, 456, 789}
    # Comma-separated string
    assert parse_owner_ids("123, 456, 789") == {123, 456, 789}
    # Space-separated string
    assert parse_owner_ids("123 456 789") == {123, 456, 789}
    # JSON array string
    assert parse_owner_ids("[123, 456, 789]") == {123, 456, 789}
    # Malformed strings or non-numeric items handled gracefully
    assert parse_owner_ids("123, abc, 456") == {123, 456}


def test_config_resolution_order_env_overrides_all(tmp_path, monkeypatch):
    # Setup json config file
    json_file = tmp_path / "config.json"
    json_file.write_text(json.dumps({
        "TOKEN": "json_token",
        "ID": 1111,
        "HASH": "json_hash",
        "STRING": "json_string",
        "OWNER_ID": [1111]
    }), encoding="utf-8")

    # Setup .env file
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TOKEN=dotenv_token\n"
        "ID=2222\n"
        "HASH=dotenv_hash\n"
        "STRING=dotenv_string\n"
        "OWNER_ID=2222\n",
        encoding="utf-8"
    )

    # Set system environment variables
    monkeypatch.setenv("TOKEN", "env_token")
    monkeypatch.setenv("ID", "3333")
    monkeypatch.setenv("HASH", "env_hash")
    monkeypatch.setenv("STRING", "env_string")
    monkeypatch.setenv("OWNER_ID", "3333, 4444")

    # Load configuration
    cfg = load_config(config_file=json_file, env_file=env_file)

    # System env variables must win
    assert cfg["TOKEN"] == "env_token"
    assert cfg["ID"] == 3333
    assert cfg["HASH"] == "env_hash"
    assert cfg["STRING"] == "env_string"
    assert cfg["OWNER_ID"] == {3333, 4444}


def test_config_resolution_order_dotenv_overrides_json(tmp_path, monkeypatch):
    # Ensure system env vars are not set
    for k in ["TOKEN", "ID", "HASH", "STRING", "OWNER_ID"]:
        monkeypatch.delenv(k, raising=False)

    json_file = tmp_path / "config.json"
    json_file.write_text(json.dumps({
        "TOKEN": "json_token",
        "ID": 1111,
        "HASH": "json_hash",
        "STRING": "json_string",
        "OWNER_ID": [1111]
    }), encoding="utf-8")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "TOKEN=dotenv_token\n"
        "ID=2222\n"
        "HASH=dotenv_hash\n"
        "STRING=dotenv_string\n"
        "OWNER_ID=2222, 5555\n",
        encoding="utf-8"
    )

    cfg = load_config(config_file=json_file, env_file=env_file)

    # .env must win over json
    assert cfg["TOKEN"] == "dotenv_token"
    assert cfg["ID"] == 2222
    assert cfg["HASH"] == "dotenv_hash"
    assert cfg["STRING"] == "dotenv_string"
    assert cfg["OWNER_ID"] == {2222, 5555}


def test_config_resolution_order_json_fallback(tmp_path, monkeypatch):
    # Ensure system env vars are not set
    for k in ["TOKEN", "ID", "HASH", "STRING", "OWNER_ID"]:
        monkeypatch.delenv(k, raising=False)

    json_file = tmp_path / "config.json"
    json_file.write_text(json.dumps({
        "TOKEN": "json_token",
        "ID": 1111,
        "HASH": "json_hash",
        "STRING": "json_string",
        "OWNER_ID": [1111]
    }), encoding="utf-8")

    # Non-existent .env file
    dummy_env = tmp_path / ".env.none"

    cfg = load_config(config_file=json_file, env_file=dummy_env)

    # Fallback to json
    assert cfg["TOKEN"] == "json_token"
    assert cfg["ID"] == 1111
    assert cfg["HASH"] == "json_hash"
    assert cfg["STRING"] == "json_string"
    assert cfg["OWNER_ID"] == {1111}


def test_config_missing_json_fallback(tmp_path, monkeypatch):
    for k in ["TOKEN", "ID", "HASH", "STRING", "OWNER_ID"]:
        monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("TOKEN", "standalone_token")
    monkeypatch.setenv("ID", "9999")
    monkeypatch.setenv("HASH", "standalone_hash")

    # File does not exist
    missing_json = tmp_path / "nonexistent.json"
    missing_env = tmp_path / "nonexistent.env"

    cfg = load_config(config_file=missing_json, env_file=missing_env)

    assert cfg["TOKEN"] == "standalone_token"
    assert cfg["ID"] == 9999
    assert cfg["HASH"] == "standalone_hash"
    assert cfg["STRING"] is None
    assert cfg["OWNER_ID"] == set()
