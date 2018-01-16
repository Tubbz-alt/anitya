# -*- coding: utf-8 -*-

from dateutil import parser
from math import ceil
import logging

import flask
from sqlalchemy.exc import SQLAlchemyError

from anitya.lib import utilities
import anitya
import anitya.forms
import anitya.lib.model

from anitya.ui import login_required, ui_blueprint
from anitya.db import Session


_log = logging.getLogger(__name__)


def is_admin(user=None):
    ''' Check if the provided user, or the user logged in are recognized
    as being admins.
    '''
    user = user or flask.g.user
    if user.is_authenticated:
        return user.admin


@ui_blueprint.route('/distro/add', methods=['GET', 'POST'])
@login_required
def add_distro():

    if not is_admin():
        flask.abort(401)

    form = anitya.forms.DistroForm()

    if form.validate_on_submit():
        name = form.name.data

        distro = anitya.lib.model.Distro(name)

        utilities.log(
            Session,
            distro=distro,
            topic='distro.add',
            message=dict(
                agent=flask.g.user.username,
                distro=distro.name,
            )
        )

        try:
            Session.add(distro)
            Session.commit()
            flask.flash('Distribution added')
        except SQLAlchemyError:
            Session.rollback()
            flask.flash(
                'Could not add this distro, already exists?', 'error')
        return flask.redirect(
            flask.url_for('anitya_ui.distros')
        )

    return flask.render_template(
        'distro_add.html',
        current='distros',
        form=form)


@ui_blueprint.route('/distro/<distro_name>/edit', methods=['GET', 'POST'])
@login_required
def edit_distro(distro_name):

    distro = anitya.lib.model.Distro.by_name(Session, distro_name)
    if not distro:
        flask.abort(404)

    if not is_admin():
        flask.abort(401)

    form = anitya.forms.DistroForm(obj=distro)

    if form.validate_on_submit():
        name = form.name.data

        if name != distro.name:
            utilities.log(
                Session,
                distro=distro,
                topic='distro.edit',
                message=dict(
                    agent=flask.g.user.username,
                    old=distro.name,
                    new=name,
                )
            )

            distro.name = name

            Session.add(distro)
            Session.commit()
            message = 'Distribution edited'
            flask.flash(message)
        return flask.redirect(
            flask.url_for('anitya_ui.distros')
        )

    return flask.render_template(
        'distro_edit.html',
        current='distros',
        distro=distro,
        form=form)


@ui_blueprint.route('/distro/<distro_name>/delete', methods=['GET', 'POST'])
@login_required
def delete_distro(distro_name):
    """ Delete a distro """

    distro = anitya.lib.model.Distro.by_name(Session, distro_name)
    if not distro:
        flask.abort(404)

    if not is_admin():
        flask.abort(401)

    form = anitya.forms.ConfirmationForm()

    if form.validate_on_submit():
        utilities.log(
            Session,
            distro=distro,
            topic='distro.remove',
            message=dict(
                agent=flask.g.user.username,
                distro=distro.name,
            )
        )

        Session.delete(distro)
        Session.commit()
        flask.flash('Distro %s has been removed' % distro_name)
        return flask.redirect(flask.url_for('anitya_ui.distros'))

    return flask.render_template(
        'distro_delete.html',
        current='distros',
        distro=distro,
        form=form)


@ui_blueprint.route('/project/<project_id>/delete', methods=['GET', 'POST'])
@login_required
def delete_project(project_id):

    project = anitya.lib.model.Project.get(Session, project_id)
    if not project:
        flask.abort(404)

    if not is_admin():
        flask.abort(401)

    project_name = project.name

    form = anitya.forms.ConfirmationForm()
    confirm = flask.request.form.get('confirm', False)

    if form.validate_on_submit():
        if confirm:
            utilities.log(
                Session,
                project=project,
                topic='project.remove',
                message=dict(
                    agent=flask.g.user.username,
                    project=project.name,
                )
            )

            for version in project.versions_obj:
                Session.delete(version)

            Session.delete(project)
            Session.commit()
            flask.flash('Project %s has been removed' % project_name)
            return flask.redirect(flask.url_for('anitya_ui.projects'))
        else:
            return flask.redirect(
                flask.url_for('anitya_ui.project', project_id=project.id))

    return flask.render_template(
        'project_delete.html',
        current='projects',
        project=project,
        form=form)


@ui_blueprint.route(
    '/project/<project_id>/delete/<distro_name>/<pkg_name>',
    methods=['GET', 'POST'])
@login_required
def delete_project_mapping(project_id, distro_name, pkg_name):

    project = anitya.lib.model.Project.get(Session, project_id)
    if not project:
        flask.abort(404)

    distro = anitya.lib.model.Distro.get(Session, distro_name)
    if not distro:
        flask.abort(404)

    package = anitya.lib.model.Packages.get(
        Session, project.id, distro.name, pkg_name)
    if not package:
        flask.abort(404)

    if not is_admin():
        flask.abort(401)

    form = anitya.forms.ConfirmationForm()
    confirm = flask.request.form.get('confirm', False)

    if form.validate_on_submit():
        if confirm:
            utilities.log(
                Session,
                project=project,
                topic='project.map.remove',
                message=dict(
                    agent=flask.g.user.username,
                    project=project.name,
                    distro=distro.name,
                )
            )

            Session.delete(package)
            Session.commit()

            flask.flash('Mapping for %s has been removed' % project.name)
        return flask.redirect(
            flask.url_for('anitya_ui.project', project_id=project.id))

    return flask.render_template(
        'regex_delete.html',
        current='projects',
        project=project,
        package=package,
        form=form)


@ui_blueprint.route(
    '/project/<project_id>/delete/<version>', methods=['GET', 'POST'])
@login_required
def delete_project_version(project_id, version):

    project = anitya.lib.model.Project.get(Session, project_id)
    if not project:
        flask.abort(404)

    version_obj = None
    for vers in project.versions_obj:
        if version == vers.version:
            version_obj = vers
            break

    if version_obj is None:
        flask.abort(
            404,
            'Version %s not found for project %s' % (version, project.name)
        )

    if not is_admin():
        flask.abort(401)

    form = anitya.forms.ConfirmationForm()
    confirm = flask.request.form.get('confirm', False)

    if form.validate_on_submit():
        if confirm:
            utilities.log(
                Session,
                project=project,
                topic='project.version.remove',
                message=dict(
                    agent=flask.g.user.username,
                    project=project.name,
                    version=version,
                )
            )

            # Delete the record of the version for this project
            Session.delete(version_obj)
            # Adjust the latest_version if needed
            if project.latest_version == version:
                project.latest_version = None
                Session.add(project)
            Session.commit()

            flask.flash('Version for %s has been removed' % version)
        return flask.redirect(
            flask.url_for('anitya_ui.project', project_id=project.id))

    return flask.render_template(
        'version_delete.html',
        current='projects',
        project=project,
        version=version,
        form=form)


@ui_blueprint.route('/logs')
@login_required
def browse_logs():

    if is_admin():
        user_logs = flask.request.args.get('user', None)
    else:
        user_logs = [flask.g.user.username, flask.g.user.email]

    from_date = flask.request.args.get('from_date', None)
    project = flask.request.args.get('project', None)
    refresh = flask.request.args.get('refresh', False)
    limit = flask.request.args.get('limit', 50)
    page = flask.request.args.get('page', 1)

    try:
        page = int(page)
    except ValueError:
        page = 1

    try:
        int(limit)
    except ValueError:
        limit = 50
        flask.flash('Incorrect limit provided, using default', 'errors')

    if from_date:
        try:
            from_date = parser.parse(from_date)
        except (ValueError, TypeError):
            flask.flash(
                'Incorrect from_date provided, using default', 'errors')
            from_date = None

    if from_date:
        from_date = from_date.date()

    offset = 0
    if page is not None and limit is not None and limit != 0:
        offset = (page - 1) * limit

    logs = []
    try:
        logs = anitya.lib.model.Log.search(
            Session,
            project_name=project or None,
            from_date=from_date,
            user=user_logs or None,
            offset=offset,
            limit=limit,
        )

        cnt_logs = anitya.lib.model.Log.search(
            Session,
            project_name=project or None,
            from_date=from_date,
            user=user_logs or None,
            count=True
        )
    except Exception as err:
        _log.exception(err)
        flask.flash(err, 'errors')

    total_page = int(ceil(cnt_logs / float(limit)))

    return flask.render_template(
        'logs.html',
        current='logs',
        refresh=refresh,
        logs=logs,
        cnt_logs=cnt_logs,
        total_page=total_page,
        page=page,
        project=project or '',
        from_date=from_date or '',
        user_logs=user_logs or ''
    )


@ui_blueprint.route('/flags')
@login_required
def browse_flags():

    if not is_admin():
        flask.abort(401)

    from_date = flask.request.args.get('from_date', None)
    state = flask.request.args.get('state', 'open')
    project = flask.request.args.get('project', None)
    flags_for_user = flask.request.args.get('user', None)
    refresh = flask.request.args.get('refresh', False)
    limit = flask.request.args.get('limit', 50)
    page = flask.request.args.get('page', 1)

    try:
        page = int(page)
    except ValueError:
        page = 1

    try:
        int(limit)
    except ValueError:
        limit = 50
        flask.flash('Incorrect limit provided, using default', 'errors')

    if from_date:
        try:
            from_date = parser.parse(from_date)
        except (ValueError, TypeError):
            flask.flash(
                'Incorrect from_date provided, using default', 'errors')
            from_date = None

    if from_date:
        from_date = from_date.date()

    offset = 0
    if page is not None and limit is not None and limit != 0:
        offset = (page - 1) * limit

    flags = []

    try:
        flags = anitya.lib.model.ProjectFlag.search(
            Session,
            project_name=project or None,
            state=state or None,
            from_date=from_date,
            user=flags_for_user or None,
            offset=offset,
            limit=limit,
        )

        cnt_flags = anitya.lib.model.ProjectFlag.search(
            Session,
            project_name=project or None,
            state=state or None,
            from_date=from_date,
            user=flags_for_user or None,
            count=True
        )
    except Exception as err:
        _log.exception(err)
        flask.flash(err, 'errors')

    total_page = int(ceil(cnt_flags / float(limit)))

    form = anitya.forms.ConfirmationForm()

    return flask.render_template(
        'flags.html',
        current='flags',
        refresh=refresh,
        flags=flags,
        cnt_flags=cnt_flags,
        total_page=total_page,
        form=form,
        page=page,
        project=project or '',
        from_date=from_date or '',
        flags_for_user=flags_for_user or '',
        state=state or ''
    )


@ui_blueprint.route('/flags/<flag_id>/set/<state>', methods=['POST'])
@login_required
def set_flag_state(flag_id, state):

    if not is_admin():
        flask.abort(401)

    if state not in ('open', 'closed'):
        flask.abort(422)

    flag = anitya.lib.model.ProjectFlag.get(Session, flag_id)

    if not flag:
        flask.abort(404)

    form = anitya.forms.ConfirmationForm()

    if form.validate_on_submit():
        try:
            utilities.set_flag_state(
                Session,
                flag=flag,
                state=state,
                user_id=flask.g.user.username,
            )
            flask.flash('Flag {0} set to {1}'.format(flag.id, state))
        except anitya.lib.exceptions.AnityaException as err:
            flask.flash(str(err), 'errors')

    return flask.redirect(
        flask.url_for('anitya_ui.browse_flags')
    )
