
from datetime import datetime, timezone
from functools import wraps
from flask import current_app

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    abort,
    session,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select, func

from extensions import db, limiter
from models import *
from services import (
    ValidationError,
    text,
    integer,
    boolean,
    email,
    safe_url,
    slug,
    payload,
    serialize_project,
)
from storage import save_upload, reference_static_asset


bp = Blueprint("admin", __name__)

# Same-cost hash verification reduces account-enumeration timing differences.
DUMMY_HASH = generate_password_hash("not-a-real-account-password")


SCHEMAS = {
    "skills": (
        Skill,
        [
            ("name", "text", True, 120),
            ("category", "text", True, 100),
            ("description", "textarea", False, 5000),
            ("level", "text", False, 100),
            ("display_order", "number", False, 100000),
        ],
    ),
    "education": (
        Education,
        [
            ("title", "text", True, 180),
            ("organization", "text", True, 180),
            ("period", "text", False, 100),
            ("description", "textarea", False, 10000),
            ("display_order", "number", False, 100000),
        ],
    ),
    "experience": (
        Experience,
        [
            ("title", "text", True, 180),
            ("organization", "text", False, 180),
            ("period", "text", False, 100),
            ("kind", "text", False, 100),
            ("description", "textarea", False, 10000),
            ("display_order", "number", False, 100000),
        ],
    ),
    "achievements": (
        Achievement,
        [
            ("title", "text", True, 180),
            ("organization", "text", False, 180),
            ("period", "text", False, 100),
            ("description", "textarea", False, 10000),
            ("display_order", "number", False, 100000),
        ],
    ),
    "categories": (
        ProjectCategory,
        [
            ("name", "text", True, 100),
            ("display_order", "number", False, 100000),
        ],
    ),
}


def schema(resource):
    if resource not in SCHEMAS:
        abort(404)
    return SCHEMAS[resource]


def assign_entry(obj, fields, data):
    for name, kind, required, maximum in fields:
        if name not in data:
            continue

        setattr(
            obj,
            name,
            integer(data[name] or 0, name)
            if kind == "number"
            else text(data, name, maximum, required),
        )

    for name, kind, required, maximum in fields:
        if required and not getattr(obj, name, None):
            raise ValidationError(name + " is required.")


def static_path_value(data, field, purpose="image"):
    """Create or retrieve an Asset for a file inside the static directory."""
    value = data.get(field, "")

    if not isinstance(value, str):
        raise ValidationError(
            f"{field} must be a relative static file path."
        )

    value = value.strip()

    if not value:
        return None

    return reference_static_asset(value, purpose)


def apply_project(p, data):
    for name in (
        "title",
        "short_description",
        "description",
        "problem",
        "objectives",
        "methodology",
        "results",
    ):
        if name in data:
            setattr(
                p,
                name,
                text(
                    data,
                    name,
                    180
                    if name == "title"
                    else 500
                    if name == "short_description"
                    else 30000,
                    name in ("title", "short_description"),
                ),
            )

    if not p.title or not p.short_description:
        raise ValidationError(
            "Title and short description are required."
        )

    if "slug" in data:
        p.slug = slug(text(data, "slug", 200, True))

    if not p.slug:
        raise ValidationError("Slug is required.")

    for name in (
        "github_url",
        "demo_url",
        "dataset_url",
        "documentation_url",
    ):
        if name in data:
            setattr(p, name, safe_url(text(data, name, 2048)))

    if "category_id" in data:
        cid = data["category_id"]
        p.category_id = (
            integer(cid, "category", 1)
            if cid not in ("", None)
            else None
        )

        if p.category_id and not db.session.get(
            ProjectCategory, p.category_id
        ):
            raise ValidationError("Category does not exist.")

    if "status" in data:
        if data["status"] not in ("draft", "published"):
            raise ValidationError("Invalid project status.")
        p.status = data["status"]

    if "featured" in data:
        p.featured = boolean(data["featured"])

    if "display_order" in data:
        p.display_order = integer(
            data["display_order"] or 0,
            "display order",
        )

    if "technologies" in data:
        names = data["technologies"]

        if isinstance(names, str):
            names = names.split(",")

        if (
            not isinstance(names, list)
            or len(names) > 30
            or any(
                not isinstance(value, str) or len(value.strip()) > 80
                for value in names
            )
        ):
            raise ValidationError(
                "Use up to 30 technology names, 80 characters each."
            )

        p.technologies = []

        for name in dict.fromkeys(
            value.strip() for value in names if value.strip()
        ):
            tech = db.session.scalar(
                select(Technology).where(Technology.name == name)
            )

            if not tech:
                tech = Technology(name=name)
                db.session.add(tech)
                db.session.flush()

            p.technologies.append(tech)

    # Remove selected gallery images.
    if "remove_image_ids" in data:
        ids = data["remove_image_ids"]

        if isinstance(ids, str):
            ids = [value for value in ids.split(",") if value]

        if not isinstance(ids, list):
            raise ValidationError("Image IDs must be a list.")

        ids = {
            integer(value, "image ID", 1)
            for value in ids
        }

        p.images[:] = [
            image for image in p.images
            if image.id not in ids
        ]

    # Reorder existing gallery images.
    if "image_order" in data:
        ids = data["image_order"]

        if isinstance(ids, str):
            ids = [value for value in ids.split(",") if value]

        if not isinstance(ids, list):
            raise ValidationError("Image order must be a list.")

        order = [
            integer(value, "image ID", 1)
            for value in ids
        ]

        for image in p.images:
            if image.id in order:
                image.display_order = order.index(image.id)

    # Update existing gallery alt text.
    for image in p.images:
        field = "image_alt_" + str(image.id)

        if field in data:
            image.alt = text(data, field, 255)

    # Thumbnail: choose a repository path OR a direct upload.
    if boolean(data.get("remove_thumbnail", False)):
        p.thumbnail = None

    thumb_path = static_path_value(data, "thumbnail_path")
    thumb_upload = request.files.get("thumbnail")

    if (
        thumb_path
        and thumb_upload
        and thumb_upload.filename
    ):
        raise ValidationError(
            "Choose either a thumbnail path or a thumbnail upload, not both."
        )

    if thumb_path:
        p.thumbnail = thumb_path
    else:
        thumb = save_upload(thumb_upload)

        if thumb:
            p.thumbnail = thumb

    # Optional gallery paths: one path per line, or comma-separated.
    gallery_paths = data.get("image_paths", "")

    if not isinstance(gallery_paths, str):
        raise ValidationError(
            "Gallery image paths must be text."
        )

    gallery_paths = [
        value.strip()
        for value in gallery_paths.replace(",", "\n").splitlines()
        if value.strip()
    ]

    uploads = [
        file
        for file in request.files.getlist("images")
        if file.filename
    ]

    if gallery_paths and uploads:
        raise ValidationError(
            "Choose either gallery paths or gallery uploads, not both."
        )

    if len(p.images) + len(gallery_paths) + len(uploads) > 20:
        raise ValidationError(
            "Maximum 20 gallery images per project."
        )

    for image_path in gallery_paths:
        asset = reference_static_asset(image_path, "image")

        p.images.append(
            ProjectImage(
                asset=asset,
                alt=p.title + " — project image",
                display_order=len(p.images),
            )
        )

    for upload in uploads:
        asset = save_upload(upload)

        p.images.append(
            ProjectImage(
                asset=asset,
                alt=p.title + " — project image",
                display_order=len(p.images),
            )
        )

    p.updated_at = datetime.now(timezone.utc)


def apply_post(post, data):
    for name in ("title", "summary", "body", "category"):
        if name in data:
            setattr(
                post,
                name,
                text(
                    data,
                    name,
                    180
                    if name == "title"
                    else 500
                    if name == "summary"
                    else 100
                    if name == "category"
                    else 100000,
                    name == "title",
                ),
            )

    if not post.title:
        raise ValidationError("Title is required.")

    if "slug" in data:
        post.slug = slug(text(data, "slug", 200, True))

    if not post.slug:
        raise ValidationError("Slug is required.")

    if "tags" in data:
        tags = (
            data["tags"].split(",")
            if isinstance(data["tags"], str)
            else data["tags"]
        )

        if (
            not isinstance(tags, list)
            or len(tags) > 30
            or any(
                not isinstance(tag, str) or len(tag) > 80
                for tag in tags
            )
        ):
            raise ValidationError("Use up to 30 short tags.")

        post.tags = list(
            dict.fromkeys(
                tag.strip() for tag in tags if tag.strip()
            )
        )

    if "status" in data:
        if data["status"] not in ("draft", "published"):
            raise ValidationError("Invalid publication status.")

        post.status = data["status"]

        if post.status == "published" and not post.published_at:
            post.published_at = datetime.now(timezone.utc)

    # Blog thumbnail: static path or upload.
    if boolean(data.get("remove_thumbnail", False)):
        post.thumbnail = None

    thumb_path = static_path_value(data, "thumbnail_path")
    thumb_upload = request.files.get("thumbnail")

    if (
        thumb_path
        and thumb_upload
        and thumb_upload.filename
    ):
        raise ValidationError(
            "Choose either a thumbnail path or a thumbnail upload, not both."
        )

    if thumb_path:
        post.thumbnail = thumb_path
    else:
        thumb = save_upload(thumb_upload)

        if thumb:
            post.thumbnail = thumb


def apply_profile(p, data):
    for name in (
        "name",
        "headline",
        "introduction",
        "about",
        "goals",
        "contact_info",
        "seo_description",
    ):
        if name in data:
            setattr(
                p,
                name,
                text(
                    data,
                    name,
                    120
                    if name == "name"
                    else 300
                    if name in ("headline", "seo_description")
                    else 10000,
                    name == "name",
                ),
            )

    if "email" in data:
        p.email = email(
            text(data, "email", 254),
            required=False,
        )

    for name in ("github_url", "linkedin_url"):
        if name in data:
            setattr(p, name, safe_url(text(data, name, 2048)))

    # Profile photo and resume: static paths or uploads.
    for name in ("photo", "resume"):
        if boolean(data.get("remove_" + name, False)):
            setattr(p, name, None)

        path_field = name + "_path"
        purpose = "resume" if name == "resume" else "profile"

        static_asset = static_path_value(
            data,
            path_field,
            purpose,
        )

        upload = request.files.get(name)

        if static_asset and upload and upload.filename:
            raise ValidationError(
                f"Choose either a {name} path or a {name} upload, not both."
            )

        if static_asset:
            setattr(p, name, static_asset)
        else:
            asset = save_upload(upload, purpose)

            if asset:
                setattr(p, name, asset)


@bp.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("5 per minute; 30 per hour", methods=["POST"])
def login_view():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        address = text(request.form, "email", 254).lower()
        password = request.form.get("password", "")

        if len(password) > 512:
            raise ValidationError("Password exceeds maximum length.")

        user = db.session.scalar(
            select(AdminUser).where(AdminUser.email == address)
        )

        valid = check_password_hash(
            user.password_hash if user else DUMMY_HASH,
            password,
        )

        if user and valid:
            session.clear()
            session.permanent = True
            login_user(user, fresh=True)
            return redirect(url_for("admin.dashboard"))

        flash("Email or password is incorrect.", "error")
        return render_template(
            "admin/login.html",
            title="Admin sign in",
        ), 401

    return render_template(
        "admin/login.html",
        title="Admin sign in",
    )


@bp.post("/admin/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("admin.login_view"))


@bp.get("/admin")
@login_required
def dashboard():
    counts = {
        name: db.session.query(Project).filter(*where).count()
        for name, where in {
            "Total projects": [],
            "Published": [Project.status == "published"],
            "Drafts": [Project.status == "draft"],
            "Featured": [Project.featured.is_(True)],
        }.items()
    }

    counts["Contact messages"] = db.session.query(
        ContactMessage
    ).count()

    recent = db.session.scalars(
        select(Project)
        .order_by(Project.updated_at.desc())
        .limit(6)
    ).all()

    return render_template(
        "admin/dashboard.html",
        title="Overview",
        counts=counts,
        recent=recent,
    )


@bp.get("/admin/projects")
@login_required
def projects():
    page = db.paginate(
        select(Project).order_by(Project.updated_at.desc()),
        page=integer(request.args.get("page", 1), "page", 1),
        per_page=20,
        error_out=False,
    )

    return render_template(
        "admin/projects.html",
        title="Projects",
        pagination=page,
    )


@bp.route("/admin/projects/new", methods=["GET", "POST"])
@bp.route("/admin/projects/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def project_form(pid=None):
    p = (
        db.get_or_404(Project, pid)
        if pid
        else Project(status="draft", featured=False, display_order=0)
    )

    if request.method == "POST":
        data = payload()
        data["featured"] = request.form.get("featured", "false")

        apply_project(p, data)
        db.session.add(p)
        db.session.commit()

        flash("Project saved.", "success")
        return redirect(url_for("admin.projects"))

    return render_template(
        "admin/project_form.html",
        title="Edit project" if pid else "New project",
        project=p,
        categories=db.session.scalars(
            select(ProjectCategory).order_by(
                ProjectCategory.display_order
            )
        ).all(),
    )


@bp.post("/admin/projects/<int:pid>/delete")
@login_required
def delete_project(pid):
    if request.form.get("confirm") != "delete":
        raise ValidationError("Deletion confirmation is required.")

    db.session.delete(db.get_or_404(Project, pid))
    db.session.commit()

    flash("Project deleted.", "success")
    return redirect(url_for("admin.projects"))


@bp.post("/admin/projects/<int:pid>/<action>")
@login_required
def project_action(pid, action):
    p = db.get_or_404(Project, pid)

    if action == "publish":
        p.status = "draft" if p.status == "published" else "published"
    elif action == "feature":
        p.featured = not p.featured
    else:
        abort(404)

    db.session.commit()
    return redirect(url_for("admin.projects"))


@bp.route("/admin/profile", methods=["GET", "POST"])
@login_required
def profile_editor():
    p = db.session.get(Profile, 1) or Profile(id=1)

    if request.method == "POST":
        apply_profile(p, payload())
        db.session.add(p)
        db.session.commit()

        flash("Profile updated.", "success")
        return redirect(url_for("admin.profile_editor"))

    return render_template(
        "admin/profile.html",
        title="Profile & resume",
        profile=p,
    )


@bp.route("/admin/content/<resource>", methods=["GET", "POST"])
@bp.route(
    "/admin/content/<resource>/<int:eid>/edit",
    methods=["GET", "POST"],
)
@login_required
def content(resource, eid=None):
    model, fields = schema(resource)
    obj = db.get_or_404(model, eid) if eid else model()

    if request.method == "POST":
        assign_entry(obj, fields, payload())
        db.session.add(obj)
        db.session.commit()

        flash("Entry saved.", "success")
        return redirect(
            url_for("admin.content", resource=resource)
        )

    return render_template(
        "admin/content.html",
        title=resource.title(),
        resource=resource,
        fields=fields,
        obj=obj,
        items=db.session.scalars(
            select(model).order_by(model.display_order, model.id)
        ).all(),
    )


@bp.post("/admin/content/<resource>/<int:eid>/delete")
@login_required
def delete_entry(resource, eid):
    model, _ = schema(resource)

    if request.form.get("confirm") != "delete":
        raise ValidationError("Deletion confirmation is required.")

    obj = db.get_or_404(model, eid)

    if model is ProjectCategory:
        for project in db.session.scalars(
            select(Project).where(Project.category_id == eid)
        ):
            project.category_id = None

    db.session.delete(obj)
    db.session.commit()

    flash("Entry deleted.", "success")
    return redirect(url_for("admin.content", resource=resource))


@bp.get("/admin/messages")
@login_required
def messages():
    query = select(ContactMessage)

    if request.args.get("archived") != "all":
        query = query.where(
            ContactMessage.archived == (
                request.args.get("archived") == "1"
            )
        )

    page = db.paginate(
        query.order_by(ContactMessage.created_at.desc()),
        page=integer(request.args.get("page", 1), "page", 1),
        per_page=20,
        error_out=False,
    )

    return render_template(
        "admin/messages.html",
        title="Inbox",
        pagination=page,
    )


@bp.post("/admin/messages/<int:mid>/<action>")
@login_required
def message_action(mid, action):
    message = db.get_or_404(ContactMessage, mid)

    if action == "archive":
        message.archived = not message.archived
    elif action == "read":
        message.read = True
    elif action == "delete":
        if request.form.get("confirm") != "delete":
            raise ValidationError("Deletion confirmation is required.")
        db.session.delete(message)
    else:
        abort(404)

    db.session.commit()

    return redirect(
        url_for(
            "admin.messages",
            archived=request.args.get("archived", ""),
        )
    )


@bp.get("/admin/blog")
@login_required
def blog():
    page = db.paginate(
        select(BlogPost).order_by(BlogPost.updated_at.desc()),
        page=integer(request.args.get("page", 1), "page", 1),
        per_page=20,
        error_out=False,
    )

    return render_template(
        "admin/blog.html",
        title="Articles",
        pagination=page,
    )


@bp.route("/admin/blog/new", methods=["GET", "POST"])
@bp.route("/admin/blog/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def blog_form(pid=None):
    post = (
        db.get_or_404(BlogPost, pid)
        if pid
        else BlogPost(status="draft")
    )

    if request.method == "POST":
        apply_post(post, payload())
        db.session.add(post)
        db.session.commit()

        flash("Article saved.", "success")
        return redirect(url_for("admin.blog"))

    return render_template(
        "admin/blog_form.html",
        title="Edit article" if pid else "New article",
        post=post,
    )


@bp.post("/admin/blog/<int:pid>/delete")
@login_required
def blog_delete(pid):
    if request.form.get("confirm") != "delete":
        raise ValidationError("Deletion confirmation is required.")

    db.session.delete(db.get_or_404(BlogPost, pid))
    db.session.commit()

    return redirect(url_for("admin.blog"))


# JSON / multipart admin API.
# Authentication and CSRF apply to every mutation.




@bp.get("/api/auth/session")
def auth_session():
    from flask import g
    from flask_wtf.csrf import generate_csrf

    authenticated = current_user.is_authenticated

    # Clear a potentially stale request-level CSRF token cache.
    g.pop("csrf_token", None)

    # Generate a token and ensure its underlying session value exists.
    token = generate_csrf()

    return jsonify(
        authenticated=authenticated,
        csrf_token=token,
    )




@bp.post("/api/auth/login")
@limiter.limit("5 per minute; 30 per hour")
def auth_login():
    data = payload()
    address = text(data, "email", 254).lower()
    password = data.get("password", "")

    if not isinstance(password, str) or len(password) > 512:
        raise ValidationError("Invalid password input.")

    user = db.session.scalar(
        select(AdminUser).where(AdminUser.email == address)
    )

    valid = check_password_hash(
        user.password_hash if user else DUMMY_HASH,
        password,
    )

    if not user or not valid:
        return jsonify(
            error={
                "code": 401,
                "message": "Email or password is incorrect.",
            }
        ), 401

    session.clear()
    session.permanent = True
    login_user(user, fresh=True)


    return jsonify(
        message="Signed in. Fetch /api/auth/session for a fresh CSRF token."
    )


@bp.post("/api/auth/logout")
@login_required
def auth_logout():
    logout_user()
    session.clear()
    return jsonify(message="Signed out.")


@bp.route("/api/admin/projects", methods=["GET", "POST"])
@bp.route(
    "/api/admin/projects/<int:pid>",
    methods=["GET", "PATCH", "DELETE"],
)
@login_required
def api_projects(pid=None):
    if request.method == "GET":
        if pid:
            return jsonify(
                data=serialize_project(
                    db.get_or_404(Project, pid), True
                )
            )

        page = db.paginate(
            select(Project).order_by(Project.updated_at.desc()),
            page=integer(request.args.get("page", 1), "page", 1),
            per_page=20,
            error_out=False,
        )

        return jsonify(
            data=[
                serialize_project(project, True)
                for project in page.items
            ],
            pagination={
                "page": page.page,
                "pages": page.pages,
                "total": page.total,
            },
        )

    if request.method == "DELETE":
        if not pid:
            abort(405)

        if payload().get("confirm") != "delete":
            raise ValidationError("Deletion confirmation is required.")

        db.session.delete(db.get_or_404(Project, pid))
        db.session.commit()
        return "", 204

    if (
        request.method == "PATCH" and not pid
    ) or (
        request.method == "POST" and pid
    ):
        abort(405)

    project = (
        db.get_or_404(Project, pid)
        if pid
        else Project(status="draft", featured=False, display_order=0)
    )

    apply_project(project, payload())
    db.session.add(project)
    db.session.commit()

    return jsonify(
        data=serialize_project(project, True)
    ), 200 if pid else 201


@bp.route("/api/admin/profile", methods=["GET", "PATCH", "POST"])
@login_required
def api_profile():
    profile = db.session.get(Profile, 1) or Profile(id=1)

    if request.method != "GET":
        apply_profile(profile, payload())
        db.session.add(profile)
        db.session.commit()

    return jsonify(
        data={
            key: getattr(profile, key)
            for key in (
                "name",
                "headline",
                "introduction",
                "about",
                "goals",
                "email",
                "contact_info",
                "github_url",
                "linkedin_url",
                "seo_description",
                "photo_id",
                "resume_id",
            )
        }
    )


@bp.route("/api/admin/content/<resource>", methods=["GET", "POST"])
@bp.route(
    "/api/admin/content/<resource>/<int:eid>",
    methods=["PATCH", "DELETE"],
)
@login_required
def api_content(resource, eid=None):
    model, fields = schema(resource)

    def serialize(obj):
        return {
            "id": obj.id,
            **{
                field[0]: getattr(obj, field[0])
                for field in fields
            },
        }

    if request.method == "GET":
        items = db.session.scalars(
            select(model).order_by(model.display_order, model.id)
        )
        return jsonify(data=[serialize(obj) for obj in items])

    obj = db.get_or_404(model, eid) if eid else model()

    if request.method == "DELETE":
        if payload().get("confirm") != "delete":
            raise ValidationError("Deletion confirmation is required.")

        if model is ProjectCategory:
            for project in db.session.scalars(
                select(Project).where(Project.category_id == eid)
            ):
                project.category_id = None

        db.session.delete(obj)
        db.session.commit()
        return "", 204

    assign_entry(obj, fields, payload())
    db.session.add(obj)
    db.session.commit()

    return jsonify(data=serialize(obj)), 200 if eid else 201


@bp.route("/api/admin/blog", methods=["GET", "POST"])
@bp.route(
    "/api/admin/blog/<int:pid>",
    methods=["GET", "PATCH", "DELETE"],
)
@login_required
def api_blog(pid=None):
    def serialize(post):
        return {
            key: getattr(post, key)
            for key in (
                "id",
                "title",
                "slug",
                "summary",
                "body",
                "category",
                "tags",
                "status",
                "thumbnail_id",
            )
        }

    if request.method == "GET":
        if pid:
            return jsonify(
                data=serialize(db.get_or_404(BlogPost, pid))
            )

        page = db.paginate(
            select(BlogPost).order_by(BlogPost.updated_at.desc()),
            page=integer(request.args.get("page", 1), "page", 1),
            per_page=20,
            error_out=False,
        )

        return jsonify(
            data=[serialize(post) for post in page.items],
            pagination={
                "page": page.page,
                "pages": page.pages,
                "total": page.total,
            },
        )

    post = (
        db.get_or_404(BlogPost, pid)
        if pid
        else BlogPost(status="draft")
    )

    if request.method == "DELETE":
        if payload().get("confirm") != "delete":
            raise ValidationError("Deletion confirmation is required.")

        db.session.delete(post)
        db.session.commit()
        return "", 204

    apply_post(post, payload())
    db.session.add(post)
    db.session.commit()

    return jsonify(data=serialize(post)), 200 if pid else 201


@bp.route("/api/admin/messages", methods=["GET"])
@bp.route(
    "/api/admin/messages/<int:mid>",
    methods=["PATCH", "DELETE"],
)
@login_required
def api_messages(mid=None):
    if request.method == "GET":
        page = db.paginate(
            select(ContactMessage).order_by(
                ContactMessage.created_at.desc()
            ),
            page=integer(request.args.get("page", 1), "page", 1),
            per_page=20,
            error_out=False,
        )

        return jsonify(
            data=[
                {
                    key: getattr(message, key)
                    for key in (
                        "id",
                        "name",
                        "email",
                        "subject",
                        "message",
                        "archived",
                        "read",
                        "created_at",
                    )
                }
                for message in page.items
            ],
            pagination={
                "page": page.page,
                "pages": page.pages,
                "total": page.total,
            },
        )

    message = db.get_or_404(ContactMessage, mid)
    data = payload()

    if request.method == "DELETE":
        if data.get("confirm") != "delete":
            raise ValidationError("Deletion confirmation is required.")

        db.session.delete(message)
        db.session.commit()
        return "", 204

    for field in ("read", "archived"):
        if field in data:
            setattr(message, field, boolean(data[field]))

    db.session.commit()
    return jsonify(message="Message updated.")
