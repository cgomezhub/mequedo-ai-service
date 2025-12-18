print("Hello World")


def change_dict(tex: str):
    dicc = {"text count": len(tex),
            "text_count_words": len(tex.split(" ")),
            "text_count_letters": len(tex.replace(" ", ""))
            }
    return dicc


print(change_dict("texto de prueba"))
