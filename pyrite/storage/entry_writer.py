"""The one function that publishes an entry file's bytes (ADR-0042 decisions 10, 12; #955).

Every write of an existing entry file ends here: ``KBService._update`` computes
the new text with ``file_operations.apply`` and publishes it with
``publish_entry_text``, which compares the file with the bytes the change was
computed on and replaces it under the momentary lock
(``atomic_write_text(expect=...)``, the lock in the repository's git dir,
§10a A1).

**A KB outside git (D1 (b), maintainer 2026-10-15).** There is no git dir to
lock in, so the file is written with compare-before-replace and no lock: the
bytes are compared with the base once, here, then replaced. Two processes
can both pass that compare and the last one wins; the result says
``locked: false`` so a caller knows. Nothing else changes: ``pyrite init``
does not run ``git init`` and ``index health`` does not warn.

``tests/test_update_walks_every_surface.py`` pins the ratchet: no other
module in ``pyrite/`` or an extension writes an entry file's bytes, except
the writers it lists, and that list only shrinks.
"""

from __future__ import annotations

import errno
import logging
import os
import secrets
from pathlib import Path
from typing import Any

from ..utils.atomic_write import ABSENT, FileChanged, _fsync_directory, atomic_write_text
from ..utils.file_lock import LOCK_TIMEOUT, NotInGitRepository

__all__ = ["FileChanged", "create_entry_text", "publish_entry_text", "publish_exclusive"]

logger = logging.getLogger(__name__)


def create_entry_text(path: str | os.PathLike[str], text: str) -> bool:
    """Write ``text`` to a path that must not exist yet; return whether the
    write ran under the lock. Raises ``FileExistsError`` when something is
    already there. Used by a create and by the templated move, the one move
    an update makes (ADR-0042 decisions 5 and 13).

    In a git work tree the absence check and the publish run under the
    momentary lock (``expect=ABSENT``). Outside one there is no lock (D1 (b)),
    so the exclusivity comes from the filesystem call that publishes
    (``publish_exclusive``: ``os.link``, else ``O_CREAT | O_EXCL``), never
    from an ``exists()`` check before it: two creates racing on one path give
    one file and one refusal in every KB kind (#391; the #974 cold read found
    the check-then-replace form let both succeed).
    """
    try:
        atomic_write_text(path, text, expect=ABSENT)
        return True
    except NotInGitRepository:
        _create_exclusive_unlocked(Path(path), text)
        return False
    except FileChanged as e:
        raise FileExistsError(str(e.path)) from e


def _create_exclusive_unlocked(target: Path, text: str) -> None:
    """The no-lock create: the bytes go to a temp file beside ``target``
    (fsynced, the mode a new file gets under the umask) and are published
    with ``publish_exclusive``; the temp file is removed on any failure."""
    target = Path(os.path.realpath(target))
    data = text.encode("utf-8")
    tmp = str(target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view) :]
            os.fsync(fd)
        finally:
            os.close(fd)
        publish_exclusive(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    _fsync_directory(target.parent)


def publish_exclusive(tmp: str, path: Path) -> None:
    """Publish ``tmp`` to ``path``, refusing if ``path`` already exists.

    The contract: publish exactly the new file at ``path`` and leave nothing
    behind that the caller cannot name, or raise and leave ``path`` as it
    was. Mechanisms, in order:

    1. ``os.link(tmp, path)``: atomic, never exposes a partial file.
       ``FileExistsError`` stops here. Any other error (no hard links on
       FAT/exFAT, EACCES on some network shares, FUSE-specific errnos) goes
       on to step 2, which is still exclusive (#391 round 3; #643 review: an
       errno allow-list here failed every create on those).
    2. ``os.open(path, O_CREAT | O_EXCL)`` claims the name, then
       ``os.replace(tmp, path)`` fills it: the replace only targets a path
       this call just created. If anything after the claim fails, the
       placeholder is removed while it is still ours (#477).
       ``FileExistsError`` stops here; so does any error other than
       "unsupported" (ENOSPC, EDQUOT, EIO...), with ``path`` untouched.
    3. Only if O_EXCL itself is unsupported (ENOTSUP, ENOSYS, EOPNOTSUPP): a
       plain ``os.replace``, guarded only by the caller's own check.

    ``tmp`` belongs to the caller until a mechanism consumes it: on success
    it is gone (moved by ``os.replace``, or unlinked after step 1; if that
    unlink fails twice the publish still succeeds and a warning names the
    leftover); on a raise it is still there and the caller removes it. The
    same mechanism ``Entry._publish_exclusive`` used for the model's save;
    it lives here now, with the one publish of a create (C2, #974 cold read).
    """
    unsupported_errnos = {errno.ENOTSUP, errno.ENOSYS}
    unsupported_errnos.add(getattr(errno, "EOPNOTSUPP", errno.ENOTSUP))

    try:
        os.link(tmp, path)
    except FileExistsError:
        raise
    except OSError:
        pass  # step 2 is still exclusive, and re-raises real I/O errors
    else:
        # Published. The cleanup sits outside the try above so an unlink
        # error is never mistaken for a link failure; one retry for a
        # transient sharing error, then a warning (a second hard link blocks
        # `ids pin` and keeps today's bytes past the next update, #752).
        try:
            os.unlink(tmp)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                logger.warning(
                    "published %s, but could not remove its temp name %s, a second "
                    "hard link to the same file; delete it by hand",
                    path,
                    tmp,
                    exc_info=True,
                )
        return

    try:
        claim_fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise
    except OSError as exc:
        if exc.errno not in unsupported_errnos:
            raise
        # Neither atomic mechanism works here; the historical best effort.
        os.replace(tmp, path)
        return

    # From here the placeholder at `path` is ours: everything up to a
    # successful replace runs inside one cleanup scope (#643 review item 3).
    claim_stat = None
    try:
        try:
            claim_stat = os.fstat(claim_fd)
        finally:
            os.close(claim_fd)
        os.replace(tmp, path)
    except BaseException:
        _remove_claim(path, claim_stat)
        raise


def _remove_claim(path: Path, claim_stat: Any) -> None:
    """Remove the O_EXCL placeholder at ``path`` if it is still ours: while it
    names the same file as ``claim_stat``, or (without one) while it is
    empty, since no entry file ever is. Best effort; the caller is raising."""
    try:
        current = os.stat(path)
        ours = (
            os.path.samestat(claim_stat, current)
            if claim_stat is not None
            else current.st_size == 0
        )
        if ours:
            os.unlink(path)
    except OSError:
        pass


def publish_entry_text(
    path: str | os.PathLike[str],
    text: str,
    *,
    expect: bytes,
    lock_timeout: float = LOCK_TIMEOUT,
) -> bool:
    """Replace ``path`` with ``text`` if it still holds ``expect``; return whether
    the replace ran under the momentary lock.

    Raises ``FileChanged`` (nothing written) when the file no longer holds
    ``expect``: the caller re-reads and re-applies. In a git work tree the
    compare and the replace run under the lock, waited for at most
    ``lock_timeout`` seconds (``LockTimeout`` after that); outside one they
    run without it (D1 (b)) and the result is ``False``.
    """
    try:
        atomic_write_text(path, text, expect=expect, lock_timeout=lock_timeout)
        return True
    except NotInGitRepository:
        target = Path(path)
        try:
            on_disk: bytes | None = target.read_bytes()
        except FileNotFoundError:
            on_disk = None
        if on_disk != expect:
            raise FileChanged(target, on_disk) from None
        atomic_write_text(path, text)
        return False
