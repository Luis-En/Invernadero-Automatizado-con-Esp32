"""Photo chunk ingestion, reassembly and serving tests."""
import binascii

FAKE_JPEG = bytes.fromhex("FFD8FFE0") + bytes(range(256)) * 3 + bytes.fromhex("FFD9")
CHUNK = 200


def _chunks(data: bytes):
    out = []
    total = (len(data) + CHUNK - 1) // CHUNK
    for index, start in enumerate(range(0, len(data), CHUNK)):
        piece = data[start:start + CHUNK]
        out.append((index, total, piece, binascii.crc_hqx(piece, 0) & 0xFFFF))
    return out


async def test_photo_chunk_crc_mismatch_rejected(client, device_headers):
    resp = await client.post(
        "/api/photos/chunk",
        params={
            "sequence": 1,
            "total_chunks": 1,
            "chunk_index": 0,
            "crc16": 1234,
            "device_id": "camera",
        },
        files={"chunk_data": ("c.bin", b"hello", "application/octet-stream")},
        headers=device_headers,
    )
    assert resp.status_code == 400


async def test_photo_chunk_out_of_range_rejected(client, device_headers):
    piece = b"abc"
    resp = await client.post(
        "/api/photos/chunk",
        params={
            "sequence": 1,
            "total_chunks": 1,
            "chunk_index": 5,
            "crc16": binascii.crc_hqx(piece, 0) & 0xFFFF,
            "device_id": "camera",
        },
        files={"chunk_data": ("c.bin", piece, "application/octet-stream")},
        headers=device_headers,
    )
    assert resp.status_code == 400


async def test_photo_reassembled_and_served(client, auth_admin, device_headers):
    chunks = _chunks(FAKE_JPEG)
    sequence = 42
    for index, total, piece, crc in chunks:
        resp = await client.post(
            "/api/photos/chunk",
            params={
                "sequence": sequence,
                "total_chunks": total,
                "chunk_index": index,
                "crc16": crc,
                "device_id": "camera",
            },
            files={"chunk_data": ("c.bin", piece, "application/octet-stream")},
            headers=device_headers,
        )
        assert resp.status_code == 200, resp.text

    latest = await client.get("/api/photos/latest", headers=auth_admin)
    assert latest.status_code == 200
    photo = latest.json()
    assert photo["is_complete"] is True
    assert photo["size_bytes"] == len(FAKE_JPEG)

    file_resp = await client.get("/api/photos/latest/file", headers=auth_admin)
    assert file_resp.status_code == 200
    assert file_resp.content == FAKE_JPEG


async def test_photos_list_requires_auth(client):
    resp = await client.get("/api/photos")

    assert resp.status_code == 401


async def test_photo_file_outside_storage_is_not_served(client, auth_admin, db):
    from app.models import Photo

    photo = Photo(
        path="/etc/passwd",
        filename="passwd",
        size_bytes=10,
        is_complete=True,
        chunks_received=1,
        chunks_total=1,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    resp = await client.get(f"/api/photos/{photo.id}/file", headers=auth_admin)
    assert resp.status_code == 404


async def test_non_jpeg_photo_is_rejected(client, device_headers):
    payload = b"this is definitely not a jpeg image"
    chunks = _chunks(payload)
    last_status = None
    for index, total, piece, crc in chunks:
        resp = await client.post(
            "/api/photos/chunk",
            params={
                "sequence": 77,
                "total_chunks": total,
                "chunk_index": index,
                "crc16": crc,
                "device_id": "camera",
            },
            files={"chunk_data": ("c.bin", piece, "application/octet-stream")},
            headers=device_headers,
        )
        last_status = resp.status_code
    assert last_status == 400
