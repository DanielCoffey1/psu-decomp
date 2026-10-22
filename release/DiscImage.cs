using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

namespace PsuRelease {
    // Read-only XDVDFS reader. No mounting, elevated privileges or external tools.
    public sealed class DiscImage : IDisposable {
        public const string SupportedXex = "93d208ee55cc89265fbc6b9e95b1cf34ae364e47df713cd9f3e8adf6101c825e";
        public sealed class Entry { public string Path; public uint Sector, Size; public bool Directory; }
        readonly FileStream stream;
        readonly HashSet<uint> directories = new HashSet<uint>();
        readonly HashSet<string> paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        readonly List<Entry> entries = new List<Entry>();
        long partition;
        public IList<Entry> Entries { get { return entries.AsReadOnly(); } }
        public long ExtractedSize { get { return entries.Where(e => !e.Directory && !IsUpdate(e.Path)).Sum(e => (long)e.Size); } }

        public DiscImage(string path) {
            stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            try {
                byte[] header = null;
                foreach (long offset in new long[] { 0, 0xFD90000, 0x2080000, 0x2000000 }) {
                    if (offset + 65572 > stream.Length) continue;
                    var candidate = Read(offset + 65536, 36);
                    if (Encoding.ASCII.GetString(candidate, 0, 20) == "MICROSOFT*XBOX*MEDIA") {
                        partition = offset; header = candidate; break;
                    }
                }
                if (header == null) throw new InvalidDataException("This is not a supported Xbox 360 XDVDFS disc image.");
                DirectoryEntries(BitConverter.ToUInt32(header, 20), BitConverter.ToUInt32(header, 24), "", 0);
                // Validate all extents before creating any output.
                foreach (var e in entries) Bounds(partition + (long)e.Sector * 2048, e.Size);
            } catch { stream.Dispose(); throw; }
        }
        void Bounds(long offset, long size) {
            if (offset < 0 || size < 0 || offset > stream.Length || size > stream.Length - offset)
                throw new InvalidDataException("Disc entry extends outside the ISO. The image may be truncated.");
        }
        byte[] Read(long offset, int size) {
            Bounds(offset, size); stream.Position = offset;
            var bytes = new byte[size]; int done = 0;
            while (done < size) { int n = stream.Read(bytes, done, size - done); if (n == 0) throw new EndOfStreamException(); done += n; }
            return bytes;
        }
        public static void ValidateName(string name) {
            if (String.IsNullOrWhiteSpace(name) || name == "." || name == ".." ||
                name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 || name.EndsWith(".") || name.EndsWith(" "))
                throw new InvalidDataException("Unsafe filename in disc or package.");
            string stem = name.Split('.')[0].ToUpperInvariant();
            if (new[] { "CON", "PRN", "AUX", "NUL", "CLOCK$" }.Contains(stem) ||
                System.Text.RegularExpressions.Regex.IsMatch(stem, @"^(COM|LPT)[0-9]$"))
                throw new InvalidDataException("Reserved Windows filename in disc or package.");
        }
        public static string SafePath(string root, string relative) {
            if (String.IsNullOrEmpty(relative) || Path.IsPathRooted(relative)) throw new InvalidDataException("Invalid relative path.");
            foreach (string part in relative.Replace('\\', '/').Split('/')) ValidateName(part);
            string prefix = Path.GetFullPath(root).TrimEnd('\\', '/') + Path.DirectorySeparatorChar;
            string result = Path.GetFullPath(Path.Combine(prefix, relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!result.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Path escapes installation folder.");
            return result;
        }
        void DirectoryEntries(uint sector, uint size, string parent, int depth) {
            if (depth > 64 || size > 16 * 1024 * 1024 || !directories.Add(sector)) throw new InvalidDataException("Invalid disc directory tree.");
            if (size == 0) return;
            byte[] table = Read(partition + (long)sector * 2048, (int)size);
            var pending = new Stack<int>(); var seen = new HashSet<int>(); pending.Push(0);
            while (pending.Count != 0) {
                int offset = pending.Pop();
                if (!seen.Add(offset) || offset < 0 || offset + 14 > table.Length) throw new InvalidDataException("Invalid disc directory node.");
                int length = table[offset + 13];
                if (offset + 14 + length > table.Length) throw new InvalidDataException("Truncated disc filename.");
                string name = Encoding.ASCII.GetString(table, offset + 14, length); ValidateName(name);
                string path = parent.Length == 0 ? name : parent + "/" + name;
                if (!paths.Add(path) || paths.Count > 200000) throw new InvalidDataException("Duplicate or excessive disc entries.");
                var e = new Entry { Path = path, Sector = BitConverter.ToUInt32(table, offset + 4), Size = BitConverter.ToUInt32(table, offset + 8), Directory = (table[offset + 12] & 16) != 0 };
                entries.Add(e);
                int left = BitConverter.ToUInt16(table, offset), right = BitConverter.ToUInt16(table, offset + 2);
                if (left != 0) pending.Push(left * 4); if (right != 0) pending.Push(right * 4);
                if (e.Directory) DirectoryEntries(e.Sector, e.Size, path, depth + 1);
            }
        }
        static bool IsUpdate(string path) { return path.Equals("$SystemUpdate", StringComparison.OrdinalIgnoreCase) || path.StartsWith("$SystemUpdate/", StringComparison.OrdinalIgnoreCase); }
        public void VerifyGame() { ReadGameExecutable(); }
        public byte[] ReadGameExecutable() {
            var xex = entries.SingleOrDefault(e => !e.Directory && e.Path.Equals("default.xex", StringComparison.OrdinalIgnoreCase));
            if (xex == null || xex.Size > 64 * 1024 * 1024) throw new InvalidDataException("Missing or invalid default.xex.");
            byte[] executable = Read(partition + (long)xex.Sector * 2048, (int)xex.Size);
            using (var hash = SHA256.Create()) {
                string actual = Hex(hash.ComputeHash(executable));
                if (actual != SupportedXex) throw new InvalidDataException("This release requires the recorded USA/Europe Xbox 360 disc revision. The ISO's default.xex does not match.\nSHA-256: " + actual);
            }
            return executable;
        }
        public static string Hex(byte[] bytes) { return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant(); }
        public static string HashFile(string path) { using (var hash = SHA256.Create()) using (var file = File.OpenRead(path)) return Hex(hash.ComputeHash(file)); }
        public void Extract(string root, Action<int, string> progress, CancellationToken cancel) {
            long total = ExtractedSize, done = 0; var buffer = new byte[1024 * 1024];
            foreach (var e in entries.OrderBy(e => e.Sector)) {
                cancel.ThrowIfCancellationRequested(); if (IsUpdate(e.Path)) continue;
                string output = SafePath(root, e.Path);
                if (e.Directory) { Directory.CreateDirectory(output); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(output));
                using (var file = new FileStream(output, FileMode.CreateNew, FileAccess.Write, FileShare.None)) {
                    stream.Position = partition + (long)e.Sector * 2048; long remaining = e.Size;
                    while (remaining > 0) {
                        cancel.ThrowIfCancellationRequested();
                        int n = stream.Read(buffer, 0, (int)Math.Min(remaining, buffer.Length));
                        if (n == 0) throw new EndOfStreamException();
                        file.Write(buffer, 0, n); remaining -= n; done += n;
                        progress(total == 0 ? 100 : (int)(done * 100 / total), e.Path);
                    }
                }
            }
        }
        public void Dispose() { stream.Dispose(); }
    }
}
