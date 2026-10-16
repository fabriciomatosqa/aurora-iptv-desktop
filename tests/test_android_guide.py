from datetime import datetime, timedelta, timezone

from aurora_desktop.catalog import LibraryV2


def stamp(dt):
    return dt.strftime("%Y%m%d%H%M%S +0000")


def test_guide_matches_display_name_when_tvg_ids_differ(tmp_path):
    playlist=tmp_path/"list.m3u"
    playlist.write_text("""#EXTM3U
#EXTINF:-1 tvg-id="sportv.rj" group-title="Esportes",SporTV HD
https://media.example.org/live/1.ts
""")
    lib=LibraryV2(tmp_path/"db.sqlite")
    pid=lib.add_playlist("Casa",str(playlist))
    lib.import_playlist(pid)
    start=datetime.now(timezone.utc)+timedelta(minutes=50)
    end=start+timedelta(hours=2)
    xml=tmp_path/"guide.xml"
    xml.write_text(f"""<tv>
      <channel id="not-identical"><display-name>SporTV FHD</display-name></channel>
      <programme channel="not-identical" start="{stamp(start)}" stop="{stamp(end)}">
        <title>Flamengo x Vasco</title><category>Brasileirão</category><live/>
      </programme>
    </tv>""",encoding="utf-8")
    lib.set_epg_url(pid,str(xml))
    assert lib.import_football(pid)==1
    events=lib.football(pid)
    assert events[0]["url"]=="https://media.example.org/live/1.ts"
    assert events[0]["broadcast"]=="live"
    assert events[0]["competition"]=="Brasileirão"


def test_guide_replay_and_nonfootball_filters(tmp_path):
    playlist=tmp_path/"list.m3u"
    playlist.write_text("#EXTM3U\n#EXTINF:-1 tvg-id=\"tv\" group-title=\"Ao Vivo\",Canal TV\nhttps://media.example.org/live/1.ts\n")
    lib=LibraryV2(tmp_path/"db.sqlite")
    pid=lib.add_playlist("Casa",str(playlist))
    lib.import_playlist(pid)
    start=datetime.now(timezone.utc)+timedelta(hours=1)
    xml=tmp_path/"guide.xml"
    xml.write_text(f"""<tv>
      <programme channel="tv" start="{stamp(start)}" stop="{stamp(start+timedelta(hours=2))}">
        <title>Botafogo x Fluminense</title><category>Campeonato Brasileiro</category>
        <previously-shown />
      </programme>
      <programme channel="tv" start="{stamp(start)}" stop="{stamp(start+timedelta(hours=2))}">
        <title>Lakers x Celtics</title><category>NBA</category>
      </programme>
    </tv>""",encoding="utf-8")
    lib.set_epg_url(pid,str(xml))
    assert lib.import_football(pid)==1
    assert lib.football(pid)[0]["broadcast"]=="replay"
