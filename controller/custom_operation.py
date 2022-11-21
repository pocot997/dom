from flask import render_template, Blueprint, request, session, redirect
from flask_marshmallow import Marshmallow
from marshmallow import fields, post_load, ValidationError, EXCLUDE
from marshmallow.validate import Length
from sqlalchemy.exc import IntegrityError

from app import db, auth
from model.base import BASIC_OPS
from model.custom_operation import CustomOperation

custom_operations = Blueprint(
    "custom_operations", __name__, template_folder="templates"
)

REDIRECTS = {
    "ADD": lambda: ("/add_custom_operation", "add_custom_operation.html"),
    "EDIT": lambda id: (f"/edit_custom_operation/{id}", "edit_custom_operation.html"),
}

ma = Marshmallow()


class OperationSchema(ma.Schema):
    op_name = fields.Str(required=True)
    argument = fields.Str(allow_none=True, validate=Length(max=127))


class CustomOperationSchema(ma.Schema):
    name = fields.Str(required=True, validate=Length(min=1, max=127))
    description = fields.Str(required=True, validate=Length(max=255))
    ops = fields.List(fields.Nested(OperationSchema()), required=True)

    @post_load
    def make_operation(self, data, **_):
        return CustomOperation(**data)


operation_schema = OperationSchema()
custom_op_schema = CustomOperationSchema()


@custom_operations.route("/custom_operations")
@auth.login_required
def all_custom_operations():
    return render_template(
        "custom_operations.html",
        custom_operations=CustomOperation.query.paginate(),
    )


@custom_operations.route("/add_custom_operation", methods=["GET"])
@auth.login_required
def add_custom_operation():
    if ("action" not in session) or (session["action"] != "CUSTOM_OP_ADD"):
        session.clear()
        session["action"] = "CUSTOM_OP_ADD"
        session["redirect"] = REDIRECTS["ADD"]()
    if "steps" not in session:
        session["steps"] = []
    custom_op = session["steps"]
    return (
        render_template(
            "add_custom_operation.html", custom_op=custom_op, basic_ops=BASIC_OPS
        ),
        200,
    )


@custom_operations.route(
    "/edit_custom_operation/<custom_operation_id>", methods=["GET"]
)
@auth.login_required
def edit_custom_operation(custom_operation_id):
    custom_operation = CustomOperation.query.get_or_404(custom_operation_id)
    if ("action" not in session) or (session["action"] != "CUSTOM_OP_EDIT"):
        session.clear()
        session["action"] = "CUSTOM_OP_EDIT"
        session["redirect"] = REDIRECTS["EDIT"](custom_operation_id)
    if ("id" not in session) or (session["id"] != custom_operation_id):
        session["id"] = custom_operation_id
        session["steps"] = custom_operation.ops
        session["redirect"] = REDIRECTS["EDIT"](custom_operation_id)
    custom_op = session["steps"]
    return (
        render_template(
            "edit_custom_operation.html",
            name=custom_operation.name,
            description=custom_operation.description,
            custom_op=custom_op,
            basic_ops=BASIC_OPS,
        ),
        200,
    )


@custom_operations.route(
    "/delete_custom_operation/<custom_operation_id>", methods=["GET"]
)
@auth.login_required
def delete_custom_operation(custom_operation_id):
    custom_operation = CustomOperation.query.get_or_404(custom_operation_id)
    db.session.delete(custom_operation)
    db.session.commit()
    message = f"Successfully deleted '{custom_operation.name}' custom operation."
    return render_template(
        "success.html", message=message, redirect="/custom_operations"
    )


ma = Marshmallow()


@custom_operations.route("/add_operation_step", methods=["POST"])
@auth.login_required
def add_operation_step():
    redirects = session["redirect"]
    if "steps" not in session:
        return redirect(redirects[0])
    custom_op = session["steps"]

    try:
        new_step = operation_schema.load(request.form, unknown=EXCLUDE)
        if new_step["op_name"] not in (op.name for op in BASIC_OPS if op.with_argument):
            new_step["argument"] = None

        custom_op.append(new_step)
        session["steps"] = custom_op
        return redirect(redirects[0])
    except ValidationError as e:
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                redirects[1],
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )


@custom_operations.route("/delete_operation_step/<index>")
@auth.login_required
def delete_operation_step(index):
    redirects = session["redirect"]
    if "steps" not in session:
        return redirect(redirects[0])
    custom_op = session["steps"]

    custom_op.pop(int(index) - 1)
    session["steps"] = custom_op
    return redirect(redirects[0])


@custom_operations.route("/clear_custom_operation")
@auth.login_required
def clear_custom_operation():
    session.clear()
    return redirect("/add_custom_operation")


@custom_operations.route("/add_custom_operation", methods=["POST"])
@auth.login_required
def create_custom_operation():
    if "steps" not in session:
        return redirect("/add_custom_operation")
    new_custom_op = request.form.to_dict()
    custom_op = session["steps"]
    new_custom_op["ops"] = custom_op

    try:
        new_custom_op = custom_op_schema.load(new_custom_op, unknown=EXCLUDE)
        db.session.add(new_custom_op)
        db.session.commit()

        session.clear()
        message = f"Successfully created '{new_custom_op.name}' custom operation."
        return render_template(
            "success.html", message=message, redirect="/custom_operations"
        )
    except ValidationError as e:
        db.session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                "add_custom_operation.html",
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        errors = ["Custom operation with this name already exists"]
        return (
            render_template(
                "add_custom_operation.html",
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )


@custom_operations.route(
    "/edit_custom_operation/<custom_operations_id>", methods=["POST"]
)
@auth.login_required
def update_custom_operation(custom_operations_id):
    if "id" not in session:
        return redirect("/edit_custom_operation")
    form = request.form.to_dict()
    custom_op = session["steps"]
    form["ops"] = custom_op

    try:
        updated = custom_op_schema.load(form, unknown=EXCLUDE)
        updated.id = int(custom_operations_id)
        db.session.merge(updated)
        db.session.commit()

        session.clear()
        message = f"Successfully updated '{updated.name}' custom operation."
        return render_template(
            "success.html", message=message, redirect="/custom_operations"
        )
    except ValidationError as e:
        db.session.rollback()
        errors = [
            f"Field '{name}': {', '.join(desc)}" for name, desc in e.messages.items()
        ]
        return (
            render_template(
                "edit_custom_operation.html",
                name=form["name"],
                description=form["description"],
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )
    except IntegrityError:
        db.session.rollback()
        errors = ["Custom operation with this name already exists"]
        return (
            render_template(
                "edit_custom_operation.html",
                name=form["name"],
                description=form["description"],
                custom_op=custom_op,
                basic_ops=BASIC_OPS,
                errors=errors,
            ),
            200,
        )
