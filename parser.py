from os import path
import pathlib
import json

loc = pathlib.Path(__file__).parent.absolute()
drink_io_folder = str(loc)


CL_CONSTANT = 0.33814


with open(path.join(drink_io_folder, 'github_recipes.json'), 'rb') as f:
    github_recipes = json.loads(f.read().decode("UTF-8").lower())


all_drink_recipes = {}
for i in github_recipes:
    lol = []
    for word in i['name'].split():
        lol.append(word.capitalize())
    name = ' '.join(lol)

    if name not in all_drink_recipes:
        all_drink_recipes[name] = {}


    new_ingredient_list = []
    for ingredient in i['ingredients']:
        if 'unit' in ingredient and ingredient['unit'] == 'cl':
            ingredient['amount'] *= CL_CONSTANT
            ingredient['amount'] = round(ingredient['amount'], 2)
            ingredient['unit'] = 'oz'
        
        shouldnt = False
        if 'unit' in ingredient and 'amount' in ingredient and 'amount' in ingredient:
            new_guy = {'ingredient': ingredient['ingredient'], 'amount': ingredient['amount'], 'unit': ingredient['unit']}
            new_ingredient_list.append(new_guy)
            shouldnt = True
        if 'special' in ingredient:
            if shouldnt:
                print('UH OH', ingredient)
                exit()
            new_guy = {'ingredient': ingredient['special'], 'amount': '???', 'unit': '???'}
            for key, value in ingredient.items():
                if key in set(['amount', 'unit', 'ingredient']):
                    continue
            new_ingredient_list.append(new_guy)
    
    all_drink_recipes[name]['ingredients'] = new_ingredient_list


with open(path.join(drink_io_folder, 'parsed_recipes.json'), 'w') as f:
    json.dump(all_drink_recipes, f, indent=2)