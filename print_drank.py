import tracking

import json


all_ingredients = {}
for row in list(tracking.DB.getAllWithDates()):
    uuid, drink_name, json_blob, timestamp, row_num = row
    dict_obj = json.loads(json_blob)
    print(type(timestamp))
    for i, oz in dict_obj.items():
        if i not in all_ingredients:
            all_ingredients[i] = 0.0
        all_ingredients[i] += oz
    
    print(f'uuid: "{uuid}" ordered a "{drink_name}" with "{json_blob}" at {timestamp} as ingredients')


x = [(val, key) for key, val in all_ingredients.items()]

x.sort()

print('=====')
for oz, ingredient in x:
    print(f'Ingredient: "{ingredient}", Oz used: "{oz}"')
