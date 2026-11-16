"""Local protected images; database revocation precedes retryable filesystem GC."""

import io
import warnings
from pathlib import Path
from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import insert
from open_webui.env import DATA_DIR
from open_webui.manual.database import table
from open_webui.manual.security import uid, now, row
from open_webui.manual.conversations import require_chat

MAX_IMAGE = 10 * 1024 * 1024
MAX_INPUT = 40 * 1024 * 1024
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
MIME = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}


def directory():
    path = Path(DATA_DIR) / 'ldt-uploads'
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def normalize(data):
    if len(data) > MAX_INPUT:
        raise HTTPException(413, 'Original image exceeds the 40 MB processing limit')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            fmt = image.format
            if fmt not in MIME or getattr(image, 'n_frames', 1) != 1:
                raise HTTPException(415, 'Use a still JPEG, PNG, or WebP image')
            if image.width * image.height > MAX_PIXELS:
                raise HTTPException(413, 'Image exceeds 40 million decoded pixels')
            image.verify()
            image = Image.open(io.BytesIO(data))
            image.load()
            if len(data) <= MAX_IMAGE:
                return data, MIME[fmt]
            image = ImageOps.exif_transpose(image).convert('RGBA' if 'A' in image.getbands() else 'RGB')
            for quality in (95, 90, 85):
                out = io.BytesIO()
                image.save(out, format='WEBP', quality=quality, method=6)
                if out.tell() <= MAX_IMAGE:
                    return out.getvalue(), 'image/webp'
            for _ in range(12):
                image.thumbnail((max(256, int(image.width * 0.85)), max(256, int(image.height * 0.85))))
                out = io.BytesIO()
                image.save(out, format='WEBP', quality=90, method=6)
                if out.tell() <= MAX_IMAGE:
                    return out.getvalue(), 'image/webp'
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, 'Invalid or unsafe image') from None
    raise HTTPException(422, 'Could not compress this image to 10 MB; choose a smaller image')


def store(conn, actor, data, prepared=None):
    content, mime = prepared if prepared is not None else normalize(data)
    fid = uid()
    path = directory() / fid
    # A failed transaction can leave an orphan file; the dedicated-directory
    # sweeper removes it after the temporary-upload grace period.
    path.write_bytes(content)
    conn.execute(
        insert(table('file')).values(
            id=fid,
            user_id=actor['id'],
            filename=fid,
            path=str(path),
            data={},
            meta={'content_type': mime, 'size': len(content)},
            created_at=now(),
            updated_at=now(),
        )
    )
    conn.execute(
        insert(table('ldt_upload')).values(
            id=fid, owner_id=actor['id'], expires_at=now() + 86400, mime=mime, size=len(content), revoked=False
        )
    )
    return {'id': fid, 'url': f'/api/v1/ldt/files/{fid}', 'size': len(content)}


def read(conn, actor, fid):
    f = row(conn, 'ldt_upload', table('ldt_upload').c.id == fid)
    if not f or f['revoked']:
        raise HTTPException(404, 'Image no longer exists')
    if f['message_id']:
        require_chat(conn, actor, f['chat_id'])
    elif f['owner_id'] != actor['id'] or f['expires_at'] <= now():
        raise HTTPException(403, 'Image access denied')
    path = directory() / fid
    if not path.is_file():
        raise HTTPException(404, 'Image file missing')
    return path.read_bytes(), f['mime']
