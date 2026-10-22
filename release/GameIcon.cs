using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace PsuRelease {
    // Reads the title image from the verified user's XEX; no artwork is bundled.
    // XEX basic compression and XDBF layout follow the pinned ReXGlue/Xenia
    // xex_module.cpp, xex2_info.h and xdbf_utils.cpp. See third_party/rexglue-LICENSE.txt.
    public static class GameIcon {
        public const string FileName = "PSU.ico";
        public const string PngHash = "783564bc3258d32068953dbaa891fa17b5fcba55c7929c1620e34714d060c181";
        static void Bounds(byte[] data, int offset, int size) {
            if (offset < 0 || size < 0 || offset > data.Length || size > data.Length - offset)
                throw new InvalidDataException("Invalid title-icon resource bounds.");
        }
        static int U16(byte[] data, int offset) { Bounds(data, offset, 2); return (data[offset] << 8) | data[offset + 1]; }
        static uint U32(byte[] data, int offset) {
            Bounds(data, offset, 4);
            return ((uint)data[offset] << 24) | ((uint)data[offset + 1] << 16) | ((uint)data[offset + 2] << 8) | data[offset + 3];
        }
        static byte[] Decrypt(byte[] data, int offset, int size, byte[] key) {
            Bounds(data, offset, size);
            using (var aes = Aes.Create()) {
                aes.Mode = CipherMode.CBC; aes.Padding = PaddingMode.None; aes.Key = key; aes.IV = new byte[16];
                using (var decryptor = aes.CreateDecryptor()) return decryptor.TransformFinalBlock(data, offset, size);
            }
        }
        public static byte[] ExtractPng(byte[] xex) {
            // Check before interpreting offsets or allocating image-sized buffers.
            using (var hash = SHA256.Create())
                if (DiscImage.Hex(hash.ComputeHash(xex)) != DiscImage.SupportedXex)
                    throw new InvalidDataException("The title icon requires the supported PSU executable.");
            var headers = new Dictionary<uint, uint>();
            for (int i = 0; i < U32(xex, 20); ++i) headers.Add(U32(xex, 24 + i * 8), U32(xex, 28 + i * 8));
            int format = checked((int)headers[0x3FF]), security = checked((int)U32(xex, 16));
            if (U16(xex, format + 4) != 1 || U16(xex, format + 6) != 1)
                throw new InvalidDataException("Unsupported title-icon image encoding.");
            int blockCount = checked(((int)U32(xex, format) - 8) / 8), dataSize = 0, imageSize = 0;
            for (int i = 0; i < blockCount; ++i) {
                int block = format + 8 + i * 8;
                dataSize = checked(dataSize + (int)U32(xex, block));
                imageSize = checked(imageSize + (int)U32(xex, block) + (int)U32(xex, block + 4));
            }
            if (imageSize > 64 * 1024 * 1024) throw new InvalidDataException("Title-icon image is too large.");
            byte[] retailKey = { 0x20, 0xB1, 0x85, 0xA5, 0x9D, 0x28, 0xFD, 0xC3, 0x40, 0x58, 0x3F, 0xBB, 0x08, 0x96, 0xBF, 0x91 };
            byte[] key = Decrypt(xex, security + 0x150, 16, retailKey);
            byte[] decrypted = Decrypt(xex, checked((int)U32(xex, 8)), dataSize, key);
            var image = new byte[imageSize]; int source = 0, destination = 0;
            for (int i = 0; i < blockCount; ++i) {
                int block = format + 8 + i * 8, size = checked((int)U32(xex, block));
                Bounds(decrypted, source, size); Bounds(image, destination, size);
                Buffer.BlockCopy(decrypted, source, image, destination, size);
                source += size; destination = checked(destination + size + (int)U32(xex, block + 4));
            }
            int resources = checked((int)headers[0x2FF]), end = checked(resources + (int)U32(xex, resources));
            for (int resource = resources + 4; resource < end; resource += 16) {
                Bounds(xex, resource, 16);
                if (Encoding.ASCII.GetString(xex, resource, 8) != "534507E3") continue;
                int start = checked((int)(U32(xex, resource + 8) - headers[0x10201]));
                int length = checked((int)U32(xex, resource + 12)); Bounds(image, start, length);
                var xdbf = new byte[length]; Buffer.BlockCopy(image, start, xdbf, 0, length);
                if (U32(xdbf, 0) != 0x58444246) throw new InvalidDataException("Missing title-icon database.");
                int count = checked((int)U32(xdbf, 12));
                int content = checked(24 + (int)U32(xdbf, 8) * 18 + (int)U32(xdbf, 16) * 8);
                for (int i = 0; i < count; ++i) {
                    int entry = 24 + i * 18;
                    if (U16(xdbf, entry) != 2 || U32(xdbf, entry + 2) != 0 || U32(xdbf, entry + 6) != 0x8000) continue;
                    int offset = checked(content + (int)U32(xdbf, entry + 10)), size = checked((int)U32(xdbf, entry + 14));
                    Bounds(xdbf, offset, size); var png = new byte[size]; Buffer.BlockCopy(xdbf, offset, png, 0, size);
                    using (var hash = SHA256.Create())
                        if (DiscImage.Hex(hash.ComputeHash(png)) != PngHash) throw new InvalidDataException("Unexpected PSU title icon.");
                    return png;
                }
            }
            throw new InvalidDataException("PSU title icon was not found.");
        }
        public static byte[] FromXex(byte[] xex) {
            byte[] png = ExtractPng(xex);
            // Windows 10/11 ICO container, preserving the original 64x64 PNG bytes.
            using (var stream = new MemoryStream()) using (var writer = new BinaryWriter(stream)) {
                writer.Write((ushort)0); writer.Write((ushort)1); writer.Write((ushort)1);
                writer.Write((byte)64); writer.Write((byte)64); writer.Write((byte)0); writer.Write((byte)0);
                writer.Write((ushort)1); writer.Write((ushort)32); writer.Write(png.Length); writer.Write(22);
                writer.Write(png); return stream.ToArray();
            }
        }
        public static void Install(string root) {
            byte[] icon = FromXex(File.ReadAllBytes(Path.Combine(root, "game", "default.xex")));
            File.WriteAllBytes(Path.Combine(root, FileName), icon);
        }
    }
}
