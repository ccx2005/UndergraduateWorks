# Object3 — AI 就业/职业规划助手

基于 DeepSeek 大模型的职业规划与就业指导脚本工具。

## 功能
- 读取历史对话与数据（chat_history.json、history_data.json）
- 调用 DeepSeek API 进行职业规划问答与建议

## 配置
复制 `config.example.json` 为 `config.json`，将 DEEPSEEK_API_KEY 填入你的真实 Key：

```bash
cp config.example.json config.json
# 编辑 config.json，填入 DEEPSEEK_API_KEY
```

> 当前仓库中的 config.json 仅含占位空 Key，请勿在仓库中填入真实密钥。

## 运行
```bash
pip install openai
python test4.py
```

## 说明
- `__pycache__/` 已被 `.gitignore` 忽略。
- 本目录由本地 `D:\PythonWork\CareerPlanning\Object3` 同步上传。
