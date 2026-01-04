# 再利用パターン - freee-partner-refiner

## 概要

このファイルはプロジェクトで発見した再利用可能なパターンを記録します。

---

## API呼び出しパターン

### freee API

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "X-Api-Version": "2020-06-15"
}
response = requests.get(url, headers=headers, params=params)
```

### gBizINFO API

```python
headers = {"X-Ho-Api-Key": api_token}
params = {"name": keyword, "limit": 5}
response = requests.get(url, headers=headers, params=params)
```

---

## 名前クリーニングパターン

### 法人格の除去

```python
name = re.sub(r'\(株\)|株式会社|（株）|有限会社|\(有\)|（有）', '', name)
```

### 店舗名の除去

```python
keywords = ['店', '支店', '営業所', 'センター', 'パーキング', '駐車場']
for kw in keywords:
    if kw in name:
        name = name.split(kw)[0]
        break
```

---

## テンプレート

```markdown
## [パターン名]

### 用途

- [どんな場面で使うか]

### コード例

\`\`\`python
# コード例
\`\`\`

### 注意点

- [使用時の注意点]
```
