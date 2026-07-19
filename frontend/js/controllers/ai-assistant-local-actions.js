/**
 * AI 管家中的本地密码生成与剪贴板操作。
 * 生成过程只在本机执行，不接触模型请求。
 */
(function () {
    function createAiAssistantLocalActions({
        aiAssistantLastResult,
        copyToClipboard,
        showToast,
        getAssistantEpoch,
        isCurrentAssistantSession
    }) {
        function secureRandomText(length, alphabet) {
            const result = [];
            const values = new Uint32Array(32);
            const limit = Math.floor(0x100000000 / alphabet.length) * alphabet.length;
            while (result.length < length) {
                window.crypto.getRandomValues(values);
                for (const value of values) {
                    if (value < limit) result.push(alphabet[value % alphabet.length]);
                    if (result.length === length) break;
                }
            }
            return result.join('');
        }

        function generateAssistantSecret() {
            const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*_-+=';
            const requestedLength = Number(aiAssistantLastResult.value?.localAction?.length);
            const length = Number.isInteger(requestedLength) && requestedLength >= 12 && requestedLength <= 64
                ? requestedLength
                : 20;
            const secret = secureRandomText(length, alphabet);
            const epoch = getAssistantEpoch();
            aiAssistantLastResult.value = {
                message: `已在本机生成 ${length} 位随机密码，内容不会发送给 AI。`,
                generatedSecret: secret
            };
            window.setTimeout(() => {
                if (isCurrentAssistantSession(epoch) && aiAssistantLastResult.value?.generatedSecret === secret) {
                    aiAssistantLastResult.value = { message: '本地生成的密码已从 AI 面板清除。' };
                }
            }, 60000);
        }

        async function copyAssistantSecret() {
            const secret = aiAssistantLastResult.value?.generatedSecret;
            if (!secret) return;
            await copyToClipboard(secret);
            showToast('本地生成的密码已复制', 'success');
        }

        return { generateAssistantSecret, copyAssistantSecret };
    }

    window.SecretBaseAiAssistantLocalActions = { createAiAssistantLocalActions };
})();
