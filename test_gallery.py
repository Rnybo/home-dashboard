from aula_client import AulaClient
import json
c = AulaClient()
albums = c.get_albums([5620584, 5620590])
for a in albums[:4]:
    print(f"id={a['id']} title={a['title']} thumbs={len(a['thumbnailsUrls'])}")
real = next((a for a in albums if a['id']), None)
if real:
    media = c.get_album_media(real['id'])
    print(f"Album '{real['title']}' media count: {len(media)}")
    if media:
        print("Media keys:", list(media[0].keys()))
        print("Sample:", json.dumps(media[0], ensure_ascii=False)[:600])
