/**
 * SecretBase 同步配对 URI 的本地解析与旧格式兼容。
 *
 * 配对链接是 bearer secret。解析只在用户点击导入后发生，不写入
 * localStorage，也不会把 WebDAV 应用密码带入 URI。
 */
(function () {
    const BASE32 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    const PREFIXES = { 1: 'SBSYNC1', 2: 'SBSYNC2' };
    const SHA256_K = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ];
    const SHA256_H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];

    function fail(message) {
        throw new Error(message);
    }

    function concatBytes(...parts) {
        const size = parts.reduce((total, part) => total + part.length, 0);
        const result = new Uint8Array(size);
        let offset = 0;
        for (const part of parts) {
            result.set(part, offset);
            offset += part.length;
        }
        return result;
    }

    function uuidBytes(value, label) {
        const normalized = String(value || '').replaceAll('-', '');
        if (!/^[0-9a-f]{32}$/i.test(normalized)) fail(`${label} 无效`);
        const result = new Uint8Array(16);
        for (let index = 0; index < result.length; index += 1) {
            result[index] = Number.parseInt(normalized.slice(index * 2, index * 2 + 2), 16);
        }
        return result;
    }

    function uuidText(bytes) {
        if (bytes.length !== 16) fail('UUID 长度无效');
        const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }

    function base64UrlBytes(value) {
        const normalized = String(value || '').replace(/-/g, '+').replace(/_/g, '/');
        if (!/^[A-Za-z0-9+/]*={0,2}$/.test(normalized)) fail('配对链接中的同步密钥无效');
        try {
            const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4);
            const binary = atob(padded);
            const result = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index += 1) result[index] = binary.charCodeAt(index);
            if (result.length !== 32) fail('配对链接中的同步密钥无效');
            return result;
        } catch (_) {
            fail('配对链接中的同步密钥无效');
        }
    }

    function base32Decode(value) {
        const normalized = String(value || '').replace(/[-\s]/g, '').toUpperCase();
        if (!normalized || !/^[A-Z2-7]+$/.test(normalized)) fail('同步恢复码格式无效');
        const result = [];
        let buffer = 0;
        let bits = 0;
        for (const character of normalized) {
            const digit = BASE32.indexOf(character);
            buffer = (buffer << 5) | digit;
            bits += 5;
            while (bits >= 8) {
                bits -= 8;
                result.push((buffer >> bits) & 0xff);
            }
        }
        if (bits > 0 && ((buffer << (8 - bits)) & 0xff) !== 0) fail('同步恢复码格式无效');
        return new Uint8Array(result);
    }

    function base32Encode(bytes) {
        let buffer = 0;
        let bits = 0;
        let encoded = '';
        for (const value of bytes) {
            buffer = (buffer << 8) | value;
            bits += 8;
            while (bits >= 5) {
                bits -= 5;
                encoded += BASE32[(buffer >> bits) & 31];
            }
        }
        if (bits > 0) encoded += BASE32[(buffer << (5 - bits)) & 31];
        return encoded;
    }

    function groupedCode(prefix, bytes) {
        const encoded = base32Encode(bytes);
        const groups = [];
        for (let index = 0; index < encoded.length; index += 5) groups.push(encoded.slice(index, index + 5));
        return `${prefix}-${groups.join('-')}`;
    }

    function utf8Bytes(value) {
        if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(value);
        const binary = unescape(encodeURIComponent(value));
        const result = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) result[index] = binary.charCodeAt(index);
        return result;
    }

    function rotateRight(value, bits) {
        return (value >>> bits) | (value << (32 - bits));
    }

    // Web Crypto 在非 HTTPS 自托管地址上可能不可用，保留一个小型本地回退。
    function sha256Fallback(input) {
        const paddedLength = ((input.length + 9 + 63) >> 6) << 6;
        const padded = new Uint8Array(paddedLength);
        padded.set(input);
        padded[input.length] = 0x80;
        const bitLength = input.length * 8;
        const high = Math.floor(bitLength / 0x100000000);
        const low = bitLength >>> 0;
        for (let index = 0; index < 4; index += 1) {
            padded[paddedLength - 8 + index] = (high >>> (24 - index * 8)) & 0xff;
            padded[paddedLength - 4 + index] = (low >>> (24 - index * 8)) & 0xff;
        }
        const state = SHA256_H.slice();
        const words = new Uint32Array(64);
        for (let offset = 0; offset < padded.length; offset += 64) {
            for (let index = 0; index < 16; index += 1) {
                const at = offset + index * 4;
                words[index] = ((padded[at] << 24) | (padded[at + 1] << 16) | (padded[at + 2] << 8) | padded[at + 3]) >>> 0;
            }
            for (let index = 16; index < 64; index += 1) {
                const value = words[index - 15];
                const other = words[index - 2];
                const sigma0 = rotateRight(value, 7) ^ rotateRight(value, 18) ^ (value >>> 3);
                const sigma1 = rotateRight(other, 17) ^ rotateRight(other, 19) ^ (other >>> 10);
                words[index] = (words[index - 16] + sigma0 + words[index - 7] + sigma1) >>> 0;
            }
            let [a, b, c, d, e, f, g, h] = state;
            for (let index = 0; index < 64; index += 1) {
                const sigma1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
                const choose = (e & f) ^ (~e & g);
                const temp1 = (h + sigma1 + choose + SHA256_K[index] + words[index]) >>> 0;
                const sigma0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
                const majority = (a & b) ^ (a & c) ^ (b & c);
                const temp2 = (sigma0 + majority) >>> 0;
                h = g;
                g = f;
                f = e;
                e = (d + temp1) >>> 0;
                d = c;
                c = b;
                b = a;
                a = (temp1 + temp2) >>> 0;
            }
            state[0] = (state[0] + a) >>> 0;
            state[1] = (state[1] + b) >>> 0;
            state[2] = (state[2] + c) >>> 0;
            state[3] = (state[3] + d) >>> 0;
            state[4] = (state[4] + e) >>> 0;
            state[5] = (state[5] + f) >>> 0;
            state[6] = (state[6] + g) >>> 0;
            state[7] = (state[7] + h) >>> 0;
        }
        const result = new Uint8Array(32);
        state.forEach((value, index) => {
            result[index * 4] = value >>> 24;
            result[index * 4 + 1] = value >>> 16;
            result[index * 4 + 2] = value >>> 8;
            result[index * 4 + 3] = value;
        });
        return result;
    }

    async function digest(bytes) {
        if (globalThis.crypto?.subtle) {
            try {
                return new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
            } catch (_) {
                // 退回到本地实现，保持离线/非 HTTPS 部署可用。
            }
        }
        return sha256Fallback(bytes);
    }

    async function validateRecoveryCode(value, version) {
        const prefix = PREFIXES[version];
        const normalized = String(value || '').trim().toUpperCase();
        if (!prefix || !normalized.startsWith(`${prefix}-`)) fail('配对链接版本与恢复码不一致，请重新生成配对信息');
        const raw = base32Decode(normalized.slice(prefix.length + 1));
        const expectedLength = version === 2 ? 69 : 53;
        if (raw.length !== expectedLength || raw[0] !== version) fail('同步恢复码版本无效');
        const body = raw.slice(0, -4);
        const checksum = raw.slice(-4);
        const expected = (await digest(concatBytes(utf8Bytes(prefix), body))).slice(0, 4);
        for (let index = 0; index < checksum.length; index += 1) {
            if (checksum[index] !== expected[index]) fail('同步恢复码校验失败');
        }
        return {
            code: groupedCode(prefix, raw),
            vaultId: uuidText(raw.slice(1, 17)),
            spaceId: version === 2 ? uuidText(raw.slice(17, 33)) : '',
        };
    }

    async function legacyRecoveryCode(uri, version) {
        const vaultId = uri.searchParams.get('vault_id');
        const spaceId = version === 2 ? uri.searchParams.get('space_id') : '';
        const key = base64UrlBytes(uri.searchParams.get('key'));
        const payload = version === 2
            ? concatBytes(Uint8Array.of(version), uuidBytes(vaultId, 'Vault ID'), uuidBytes(spaceId, '同步空间 ID'), key)
            : concatBytes(Uint8Array.of(version), uuidBytes(vaultId, 'Vault ID'), key);
        const prefix = PREFIXES[version];
        const checksum = (await digest(concatBytes(utf8Bytes(prefix), payload))).slice(0, 4);
        return groupedCode(prefix, concatBytes(payload, checksum));
    }

    async function parse(rawValue) {
        const raw = String(rawValue || '').trim();
        if (!raw) fail('请先粘贴 SecretBase 配对链接');
        let uri;
        try {
            uri = new URL(raw);
        } catch (_) {
            fail('配对链接格式无效');
        }
        if (uri.protocol !== 'secretbase:' || uri.hostname !== 'sync' || uri.pathname !== '/join' || uri.hash || uri.username || uri.password) {
            fail('链接不是 SecretBase 同步配对链接');
        }
        for (const key of ['v', 'url', 'username', 'recovery_code', 'key', 'vault_id', 'space_id']) {
            if (uri.searchParams.getAll(key).length > 1) fail(`配对链接包含重复的 ${key} 参数`);
        }
        for (const key of ['password', 'webdav_password', 'app_password', 'token']) {
            if (uri.searchParams.has(key)) fail('配对链接不得包含 WebDAV 应用密码或访问令牌');
        }
        const version = Number(uri.searchParams.get('v'));
        if (version !== 1 && version !== 2) fail('仅支持 V1/V2 SecretBase 同步配对链接');
        const baseUrl = String(uri.searchParams.get('url') || '').trim();
        const username = String(uri.searchParams.get('username') || '').trim();
        let webdav;
        try {
            webdav = new URL(baseUrl);
        } catch (_) {
            fail('配对链接中的 WebDAV 地址无效');
        }
        if (webdav.protocol !== 'https:' || !webdav.hostname || webdav.username || webdav.password || webdav.search || webdav.hash || !username) {
            fail('配对链接中的 WebDAV 信息无效');
        }
        const recoveryValue = uri.searchParams.get('recovery_code');
        if (recoveryValue && uri.searchParams.has('key')) fail('配对链接包含重复的同步密钥材料，请重新生成');
        const recovery = recoveryValue || await legacyRecoveryCode(uri, version);
        const validated = await validateRecoveryCode(recovery, version);
        const declaredVault = uri.searchParams.get('vault_id');
        const declaredSpace = uri.searchParams.get('space_id');
        if (declaredVault && declaredVault.toLowerCase() !== validated.vaultId) fail('配对链接中的 Vault 身份与恢复码不一致');
        if (version === 2 && declaredSpace && declaredSpace.toLowerCase() !== validated.spaceId) fail('配对链接中的同步空间身份与恢复码不一致');
        return {
            version,
            baseUrl,
            username,
            recoveryCode: validated.code,
        };
    }

    window.SecretBaseSyncPairing = { parse };
})();
