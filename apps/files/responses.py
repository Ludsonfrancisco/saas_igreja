"""Construcao da resposta de download por streaming (Sprint 6 / Bloco 3, OD-021).

Isolado da view para deixar EXPLICITA e testavel a garantia "sem URL publica":
abrimos o arquivo direto do storage (`file_asset.file.open`) e devolvemos os bytes
via `FileResponse`. NUNCA chamamos `file_asset.file.url` nem redirecionamos para o
storage — o cliente jamais recebe um link direto do objeto (RNF-018 / RISK-005 /
`test_no_permanent_public_url`).

`Content-Type` vem do `mime_type` detectado por magic bytes no upload (Bloco 2),
nao da extensao. `Content-Disposition: attachment` forca download com o nome
original sanitizado, evitando renderizacao inline (defesa extra contra qualquer
conteudo que o browser tentasse interpretar).
"""

from django.http import FileResponse


def stream_file_asset(file_asset):
    """Devolve um `FileResponse` que faz streaming do binario do `FileAsset`.

    O arquivo e aberto a partir do `STORAGES['default']` (FS em dev, R2 em prod) e
    transmitido pela propria resposta — sem expor a URL do storage. `FileResponse`
    fecha o handle do arquivo ao terminar de servir.
    """
    file_handle = file_asset.file.open('rb')
    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=file_asset.filename,
        content_type=file_asset.mime_type or 'application/octet-stream',
    )
