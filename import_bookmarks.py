from html.parser import HTMLParser
import sqlite3


class BookmarkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag = None
        self.in_h3 = False
        self.in_a = False
        self.current_name = ""
        self.current_href = ""
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "h3":
            self.in_h3 = True
            self.tag = ""

        elif tag == "a":
            self.in_a = True
            self.current_name = ""
            self.current_href = attrs.get("href", "")

    def handle_endtag(self, tag):
        if tag == "h3":
            self.in_h3 = False

        elif tag == "a":
            self.in_a = False

            self.links.append({
                "nome": self.current_name.strip(),
                "link": self.current_href,
                "tag": self.tag.strip(),
            })

    def handle_data(self, data):
        if self.in_h3:
            self.tag += data
        elif self.in_a:
            self.current_name += data


with open("musicas.html", encoding="utf-8") as f:
    parser = BookmarkParser()
    parser.feed(f.read())


conn = sqlite3.connect("musicas.db")

conn.execute("PRAGMA foreign_keys = ON")


with conn:
    for song in parser.links:
        try:
            # Get/create tag
            conn.execute(
                "INSERT OR IGNORE INTO tags (nome) VALUES (?)",
                (song["tag"],)
            )

            row = conn.execute(
                "SELECT id FROM tags WHERE nome = ?",
                (song["tag"],)
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    f"Tag was not found after insertion: {song['tag']!r}"
                )

            tag_id = row[0]

            # Insert song
            cursor = conn.execute(
                """
                INSERT INTO musicas (nome, link)
                VALUES (?, ?)
                """,
                (song["nome"], song["link"])
            )

            musica_id = cursor.lastrowid

            # Associate song with tag
            conn.execute(
                """
                INSERT INTO musicas_tags (musica_id, tag_id)
                VALUES (?, ?)
                """,
                (musica_id, tag_id)
            )

        except sqlite3.IntegrityError as e:
            print(
                f"[INTEGRITY ERROR] "
                f"{e} FOR ({song['nome']!r}, '{song['link']}')"
            )

        except sqlite3.Error as e:
            print(
                f"[SQLITE ERROR] - "
                f"{e} FOR ({song['nome']!r}, '{song['link']}')"
            )

        except Exception as e:
            print(
                f"[UNEXPECTED ERROR] - "
                f"{e} FOR ({song['nome']!r}, '{song['link']}')"
            )


conn.close()
