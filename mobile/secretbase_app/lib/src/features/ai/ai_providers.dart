class AiProviderPreset {
  const AiProviderPreset({
    required this.id,
    required this.name,
    required this.baseUrl,
    this.aggregator = false,
  });

  final String id;
  final String name;
  final String baseUrl;
  final bool aggregator;
}

const aiProviderPresets = <AiProviderPreset>[
  AiProviderPreset(
    id: 'openai',
    name: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
  ),
  AiProviderPreset(
    id: 'deepseek',
    name: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com',
  ),
  AiProviderPreset(
    id: 'kimi',
    name: 'Kimi',
    baseUrl: 'https://api.moonshot.cn/v1',
  ),
  AiProviderPreset(
    id: 'zhipu',
    name: '智谱 GLM',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
  ),
  AiProviderPreset(
    id: 'siliconflow',
    name: 'SiliconFlow',
    baseUrl: 'https://api.siliconflow.cn/v1',
  ),
  AiProviderPreset(
    id: 'gemini',
    name: 'Gemini',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
  ),
  AiProviderPreset(
    id: 'openrouter',
    name: 'OpenRouter',
    baseUrl: 'https://openrouter.ai/api/v1',
    aggregator: true,
  ),
  AiProviderPreset(id: 'custom', name: '自定义 OpenAI 兼容接口', baseUrl: ''),
];

AiProviderPreset aiProviderById(String id) => aiProviderPresets.firstWhere(
  (provider) => provider.id == id,
  orElse: () => aiProviderPresets.last,
);

String inferAiProviderId(String baseUrl) {
  final uri = Uri.tryParse(baseUrl.trim());
  if (uri == null || uri.host.isEmpty) return 'custom';
  for (final provider in aiProviderPresets) {
    final providerUri = Uri.tryParse(provider.baseUrl);
    if (providerUri != null && providerUri.host == uri.host) return provider.id;
  }
  return 'custom';
}
