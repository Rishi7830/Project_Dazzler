def genrecolor():
    genres_to_color ={"Blues":["Blue","Grey","Purple","Cyan","Black"],
                      "Classical":["White","Blue","Green","Grey","Yellow"],
                      "Country":["Green","Brown","Yellow","Orange","Blue"],
                      "Electronica and Dance":["Cyan","Pink","Yellow","Red","Purple"],
                      "Folk":["Green","Brown","Grey","Yellow","Blue"],
                      "Gospel":["White","Purple","Grey","Green","Black"],
                      "Hip-Hop and Rap":["Red", "Black", "Orange", "Purple", "Yellow"],
                      "Indie":["Black", "Purple", "Green", "Red", "Cyan"],
                      "Jazz":["Blue", "Grey", "Purple", "Brown", "Orange"],
                      "Latin":["Red", "Yellow", "Orange", "Pink", "Brown"],
                      "Metal":["Black", "Red", "Grey", "Purple", "Brown"],
                      "Pop":["Pink", "Red", "Orange", "Yellow", "Blue"],
                      "Reggae":["Orange","Green","Yellow","Brown","Red"],
                      "Rock":["Red", "Black", "Purple", "Blue", "Grey"],
                      "Soul":["Orange", "Pink", "Purple", "Brown", "Red"]}
    color_to_hex = {"Blue":"#0000FF",
                    "Orange":"#FE9900",
                    "Red":"#FF0000",
                    "Green":"#00FF00",
                    "Yellow":"FFDE59",
                    "Pink":"#FFC0CB",
                    "White":"#FFFFFF",
                    "Black":"#000000",
                    "Brown":"#8D6F64",
                    "Grey":"#CECECE",
                    "Purple":"#CC6CE7",
                    "Cyan":"#00FFFF"}
    print("Choose a genre from:")
    print(genres_to_color.keys())
    inp = input("Enter a genre: ")
    print("The colors which will be used are: ")
    print(genres_to_color[inp])
    return genres_to_color[inp]
