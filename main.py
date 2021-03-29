import os
import random
import string

import flask.views
import flask_marshmallow
import flask_sqlalchemy
import marshmallow

# I wouldn't use flask sqlalchemy but rather sqlalchemy directly because:
#  1. It couples database code to Flask
#  2. It doesn't provide much functionality
db = flask_sqlalchemy.SQLAlchemy()

# Same thing for marshmallow, althought less strongly, at the end is
#  everything part of the view layer
ma = flask_marshmallow.Marshmallow()


# model.py
class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=100), unique=True)
    recipes = db.relationship(
        "Recipe",
        secondary=lambda: ingredient_recipe_table,
        back_populates="ingredients",
    )


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(length=100), unique=True)
    ingredients = db.relationship(
        "Ingredient",
        secondary=lambda: ingredient_recipe_table,
        back_populates="recipes",
    )


ingredient_recipe_table = db.Table(
    "ingredient_recipe",
    db.metadata,
    db.Column("ingredient_id", db.Integer, db.ForeignKey("recipe.id")),
    db.Column("recipe_id", db.Integer, db.ForeignKey("ingredient.id")),
)


# serializer.py
class IngredientSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Ingredient

    id = ma.auto_field()
    name = ma.auto_field()


ingredient_schema = IngredientSchema()
ingredients_schema = IngredientSchema(many=True)


class RecipeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Recipe
        include_fk = True

    id = ma.auto_field()
    name = ma.auto_field()
    ingredients = ma.auto_field(only=("id",))


recipe_schema = RecipeSchema()
recipes_schema = RecipeSchema(many=True)

# api.py

bp = flask.Blueprint("api", __name__)


class RecipesView(flask.views.MethodView):
    def get(self):
        if not flask.request.args or not (
            ingredients := flask.request.args.get("ingredient")
        ):
            matching_recipes = db.session.query(Recipe)
        else:
            matching_recipes = db.session.query(Recipe).filter(
                Recipe.ingredients.any(name=ingredients)
            )
        response = recipes_schema.jsonify(matching_recipes)
        return response

    def post(self):
        json_data = flask.request.get_json()
        if not json_data:
            return {"error": "No data"}, 400
        try:
            recipe_data = recipe_schema.load(json_data, session=db.session)
        except marshmallow.ValidationError as err:
            return err.messages, 422

        db.session.add_all(recipe_data["ingredients"])
        db.session.flush()

        recipe = (
            db.session.query(Recipe)
            .filter(Recipe.name == recipe_data["name"])
            .one_or_none()
        )
        if recipe:
            return flask.jsonify({"error": "Recipe already exists"}), 400
        recipe = Recipe(**recipe_data)
        db.session.merge(recipe)
        db.session.commit()

        recipe = recipe_schema.dump(
            db.session.query(Recipe).filter(Recipe.id == recipe.id).one()
        )
        return recipe, 201


bp.add_url_rule("/recipes/", view_func=RecipesView.as_view("recipes"))


class RecipeView(flask.views.MethodView):
    def get(self, id):
        recipe = db.session.query(Recipe).filter(Recipe.id == id).one_or_none()
        if not recipe:
            return {"error": f"No recipe with id {id}"}, 404
        return recipe_schema.jsonify(recipe)

    def put(self, id):
        recipe = db.session.query(Recipe).filter(Recipe.id == id).one_or_none()
        if not recipe:
            return {"error": f"No recipe with id {id}"}, 404
        json_data = flask.request.get_json()
        if not json_data:
            return {"error": "No data"}, 400
        try:
            updated_recipe_data = recipe_schema.load(json_data, session=db.session)
        except marshmallow.ValidationError as err:
            return err.messages, 422

        recipe.name = updated_recipe_data["name"]
        recipe.ingredients = updated_recipe_data["ingredients"]

        # There should be more validation here
        db.session.merge(recipe)
        db.session.commit()

        return recipe_schema.jsonify(recipe)

    def delete(self, id):
        recipe = db.session.query(Recipe).filter(Recipe.id == id).one_or_none()
        if not recipe:
            return {"error": f"No recipe with id {id}"}, 404
        db.session.delete(recipe)
        db.session.commit()
        return {"message": "Deleted"}, 200


bp.add_url_rule("/recipes/<int:id>", view_func=RecipeView.as_view("recipe"))


def create_app():
    app = flask.Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "mysql+mysqldb://root@127.0.0.1/db"
    )
    db.init_app(app)
    ma.init_app(app)
    app.register_blueprint(bp, url_prefix="/")
    db.create_all(app=app)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run("localhost", 8000, debug=True)


def test_recipes():
    app = create_app()
    cli = app.test_client()

    recipe_name = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    ingredient_names = [
        "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        for _ in range(5)
    ]

    # Create
    response = cli.post(
        "/recipes/",
        json={
            "name": recipe_name,
            "ingredients": [{"name": n} for n in ingredient_names],
        },
    )
    assert response.status_code == 201, response.json
    recipe = response.json

    # At least one item
    response = cli.get("/recipes/")
    assert response.status_code == 200, response.json
    assert len(response.json)

    # Get the recipe by id
    response = cli.get(f"/recipes/{recipe['id']}")
    assert response.status_code == 200, response.json
    assert response.json == recipe

    # Get the recipe by ingredient
    response = cli.get(f"/recipes/?ingredient={ingredient_names[0]}")
    assert response.status_code == 200, response.json
    assert len(response.json) == 1, response.json
    assert response.json[0] == recipe

    response = cli.get(
        f"/recipes/?ingredient={ingredient_names[0]}&ingredient={ingredient_names[1]}"
    )
    assert response.status_code == 200, response.json
    assert len(response.json) == 1, response.json
    assert response.json[0] == recipe

    # Update
    ingredients = recipe["ingredients"]
    response = cli.put(
        f"/recipes/{recipe['id']}",
        json={
            "name": recipe_name + "AAA",
            "ingredients": [i for i in ingredients[:-1]],
        },
    )
    assert response.status_code == 200, response.json
    assert response.json != recipe

    # Delete
    response = cli.delete(
        f"/recipes/{recipe['id']}",
    )
    assert response.status_code == 200, response.json

    # Ensure it is no longer there
    response = cli.get(f"/recipes/{recipe['id']}")
    assert response.status_code == 404, response.json
