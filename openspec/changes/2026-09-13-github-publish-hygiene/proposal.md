# Proposal: GitHub publish hygiene

## Why

Репозиторий готовится к публикации на GitHub. В OpenSpec накопились дневные change-папки с внутренними именами кластера, старым требованием хранить брокерский пароль в K8s Secret и ссылками на локальный `registry.selectel`. Файлы с credentials не должны попасть в публичный git.

## What

- Свернуть историю `openspec/changes/*` в каноническую spec
- Убрать из spec привязку к конкретному kube-context/registry path как к обязательным константам
- Документировать, что `.mcp.json` локальный и gitignored; в репо остаются example-файлы
- Расширить `.gitignore` (registry, env, keys, kubeconfig, `.mcp.json`)
- Добавить `registry.selectel.example` и `ingress_host.example`

## Impact

- **Затронутые spec-домены:** `webquik-mcp`
- **Код:** `.gitignore`, example-файлы, `openspec/`
- **Риски:** оператор должен скопировать example → локальный файл перед деплоем

## Out of scope

- Ротация уже выпущенных registry-токенов (делается вручную в Selectel)
- Вынос персональных hostname из `k8s/` и README в шаблоны
- Инициализация git remote / создание GitHub repo
