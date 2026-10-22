# Public release packaging

Before making the repository public, the preview.1 through preview.4 downloads
were repackaged on October 22, 2026 to remove local build paths embedded in
native diagnostic strings. The game executable and GPU plugin were rebuilt
with compiler file-prefix mappings. Game logic, launcher features and the
runtime libraries were retained for each version.

Each replacement source ZIP includes its original version's source with the
file-prefix mappings and release privacy check added. Its build-info.json keeps
the original source commit, marks source_modified as true and records the
privacy repack. The source ZIP is the build reference for these replacement
downloads. Release tags and earlier Git history retain their original meaning.

The installer embeds the corrected payload and checksums. Download the current
SHA256SUMS.txt alongside the installer: hashes from the original private
downloads no longer apply. Previously installed copies continue to work.

New packages run tools/check-release-privacy.ps1 against the unpacked payload
and source snapshot before compression. It rejects local user-directory paths
in text and embedded ASCII/UTF-16 strings. This path check complements secret
scanning; it is not a general detector for every kind of personal information.

The pre-publication audit covered reachable Git history, release sources and
embedded installer payloads, and repository discussions/automation metadata.
The credential scan's findings were reviewed as SDK checksum false positives.
No credentials, personal saves or original disc assets were found in the
audited material. The owner's existing public GitHub identity remains visible.
