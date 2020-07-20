# -*- coding: utf-8 -*-

import logging
import os
import re
import stat

from pkg_resources import parse_version

import pytest

from pyscaffold import utils
from pyscaffold.exceptions import InvalidIdentifier
from pyscaffold.log import logger

from .helpers import temp_umask, uniqpath, uniqstr


def test_chdir(caplog, tmpdir, isolated_logger):
    caplog.set_level(logging.INFO)
    curr_dir = os.getcwd()
    dname = uniqstr()  # Use a unique name to get easily identifiable logs
    temp_dir = str(tmpdir.mkdir(dname))
    with utils.chdir(temp_dir, log=True):
        new_dir = os.getcwd()
    assert new_dir == os.path.realpath(temp_dir)
    assert curr_dir == os.getcwd()
    assert curr_dir != new_dir
    logs = caplog.text
    assert re.search("chdir.+" + dname, logs)


def test_pretend_chdir(caplog, tmpdir):
    caplog.set_level(logging.INFO)
    curr_dir = os.getcwd()
    dname = uniqstr()  # Use a unique name to get easily identifiable logs
    temp_dir = str(tmpdir.mkdir(dname))
    with utils.chdir(temp_dir, pretend=True):
        new_dir = os.getcwd()
    assert new_dir == curr_dir  # the directory is not changed
    assert curr_dir == os.getcwd()
    logs = caplog.text
    assert re.search("chdir.+" + dname, logs)


def test_is_valid_identifier():
    bad_names = [
        "has whitespace",
        "has-hyphen",
        "has_special_char$",
        "1starts_with_digit",
    ]
    for bad_name in bad_names:
        assert not utils.is_valid_identifier(bad_name)
    valid_names = ["normal_variable_name", "_private_var", "_with_number1"]
    for valid_name in valid_names:
        assert utils.is_valid_identifier(valid_name)


def test_make_valid_identifier():
    assert utils.make_valid_identifier("has whitespaces ") == "has_whitespaces"
    assert utils.make_valid_identifier("has-hyphon") == "has_hyphon"
    assert utils.make_valid_identifier("special chars%") == "special_chars"
    assert utils.make_valid_identifier("UpperCase") == "uppercase"
    with pytest.raises(InvalidIdentifier):
        utils.make_valid_identifier("def")


def test_exceptions2exit():
    @utils.exceptions2exit([RuntimeError])
    def func(_):
        raise RuntimeError("Exception raised")

    with pytest.raises(SystemExit):
        func(1)


def test_exceptions2exit_verbose(capsys):
    @utils.exceptions2exit([RuntimeError])
    def func(_):
        logger.level = logging.DEBUG
        raise RuntimeError("Exception raised")

    with pytest.raises(SystemExit):
        func(1)
    error = capsys.readouterr().err
    match = re.search(r"raise RuntimeError", error)
    assert match


def test_levenshtein():
    s1 = "born"
    s2 = "burn"
    assert utils.levenshtein(s1, s2) == 1
    s2 = "burnt"
    assert utils.levenshtein(s1, s2) == 2
    assert utils.levenshtein(s2, s1) == 2
    s2 = ""
    assert utils.levenshtein(s2, s1) == 4


def test_prepare_namespace():
    namespaces = utils.prepare_namespace("com")
    assert namespaces == ["com"]
    namespaces = utils.prepare_namespace("com.blue_yonder")
    assert namespaces == ["com", "com.blue_yonder"]
    with pytest.raises(InvalidIdentifier):
        utils.prepare_namespace("com.blue-yonder")


def test_create_file(tmpfolder):
    file = utils.create_file("a-file.txt", "content")
    assert file.is_file()
    assert tmpfolder.join("a-file.txt").read() == "content"


def test_pretend_create_file(tmpfolder, caplog):
    caplog.set_level(logging.INFO)
    fname = uniqstr()  # Use a unique name to get easily identifiable logs
    # When a file is created with pretend=True,
    file = utils.create_file(fname, "content", pretend=True)
    # Then it should not be written to the disk,
    assert not file.exists()
    assert tmpfolder.join(fname).check() is False
    # But the operation should be logged
    logs = caplog.text
    assert re.search("create.+" + fname, logs)


def test_create_directory(tmpfolder):
    folder = utils.create_directory("a-dir")
    assert folder.is_dir()
    assert tmpfolder.join("a-dir").check(dir=1)


def test_pretend_create_directory(tmpfolder, caplog):
    caplog.set_level(logging.INFO)
    dname = uniqstr()  # Use a unique name to get easily identifiable logs
    # When a directory is created with pretend=True,
    folder = utils.create_directory(dname, pretend=True)
    # Then it should not appear in the disk,
    assert not folder.exists()
    assert tmpfolder.join(dname).check() is False
    # But the operation should be logged
    logs = caplog.text
    assert re.search("create.+" + dname, logs)


def test_chmod(tmpfolder):
    _ = tmpfolder  # just for chdir

    # Windows have problems with executable bits, so let's just exercise R and W
    with temp_umask(0o333):
        file = uniqpath()
        file.touch()
        assert stat.S_IMODE(file.stat().st_mode) == 0o444
        utils.chmod(file, 0o666)
        assert stat.S_IMODE(file.stat().st_mode) == 0o666


def test_pretend_chmod(tmpfolder, caplog):
    _ = tmpfolder  # just for chdir
    caplog.set_level(logging.INFO)

    # Windows have problems with executable bits, so let's just exercise R and W
    with temp_umask(0o333):
        file = uniqpath()
        file.touch()
        assert stat.S_IMODE(file.stat().st_mode) == 0o444
        # When calling chmod on a file with pretend
        utils.chmod(file, 0o777, pretend=True)
        # It should not change access permissions
        assert stat.S_IMODE(file.stat().st_mode) == 0o444
        # But the operation should be logged
        logs = caplog.text
        assert re.search(f"chmod 777.+{file}", logs)


def test_move(tmpfolder):
    # Given a file or directory exists,
    tmpfolder.join("a-file.txt").write("text")
    tmpfolder.join("a-folder").ensure_dir()
    tmpfolder.join("a-folder/another-file.txt").write("text")
    # When it is moved,
    tmpfolder.join("a-dir").ensure_dir()
    utils.move("a-file.txt", target="a-dir")
    utils.move("a-folder", target="a-dir")
    # Then the original path should not exist
    assert not tmpfolder.join("a-file.txt").check()
    assert not tmpfolder.join("a-folder").check()
    # And the new path should exist
    assert tmpfolder.join("a-dir/a-file.txt").check()
    assert tmpfolder.join("a-dir/a-folder/another-file.txt").check()


def test_move_multiple_args(tmpfolder):
    # Given several files exist,
    tmpfolder.join("a-file.txt").write("text")
    tmpfolder.join("another-file.txt").write("text")
    assert not tmpfolder.join("a-dir/a-file.txt").check()
    assert not tmpfolder.join("a-dir/another-file.txt").check()
    # When they are moved together,
    tmpfolder.join("a-dir").ensure_dir()
    utils.move("a-file.txt", "another-file.txt", target="a-dir")
    # Then the original paths should not exist
    assert not tmpfolder.join("a-file.txt").check()
    assert not tmpfolder.join("another-file.txt").check()
    # And the new paths should exist
    assert tmpfolder.join("a-dir/a-file.txt").read() == "text"
    assert tmpfolder.join("a-dir/another-file.txt").read() == "text"


def test_move_non_dir_target(tmpfolder):
    # Given a file exists,
    tmpfolder.join("a-file.txt").write("text")
    assert not tmpfolder.join("another-file.txt").check()
    # When it is moved,
    utils.move("a-file.txt", target="another-file.txt")
    # Then the original path should not exist
    assert not tmpfolder.join("a-file.txt").check()
    # And the new path should exist
    assert tmpfolder.join("another-file.txt").read() == "text"

    # Given a dir exists,
    tmpfolder.join("a-dir").ensure_dir()
    tmpfolder.join("a-dir/a-file.txt").write("text")
    assert not tmpfolder.join("another-dir/a-file.txt").check()
    # When it is moved to a path that do not exist yet,
    utils.move("a-dir", target="another-dir")
    # Then the dir should be renamed.
    assert not tmpfolder.join("a-dir").check()
    assert tmpfolder.join("another-dir/a-file.txt").read() == "text"


def test_move_log(tmpfolder, caplog):
    caplog.set_level(logging.INFO)
    fname1 = uniqstr()  # Use a unique name to get easily identifiable logs
    fname2 = uniqstr()
    dname = uniqstr()
    # Given a file or directory exists,
    tmpfolder.join(fname1).write("text")
    tmpfolder.join(fname2).write("text")
    # When it is moved without log kwarg,
    tmpfolder.join(dname).ensure_dir()
    utils.move(fname1, target=dname)
    # Then no log should be created.
    logs = caplog.text
    assert not re.search("move.+{}.+to.+{}".format(fname1, dname), logs)
    # When it is moved with log kwarg,
    utils.move(fname2, target=dname, log=True)
    # Then log should be created.
    logs = caplog.text
    assert re.search("move.+{}.+to.+{}".format(fname2, dname), logs)


def test_pretend_move(tmpfolder):
    # Given a file or directory exists,
    tmpfolder.join("a-file.txt").write("text")
    tmpfolder.join("another-file.txt").write("text")
    # When it is moved without pretend kwarg,
    tmpfolder.join("a-dir").ensure_dir()
    utils.move("a-file.txt", target="a-dir")
    # Then the src should be moved
    assert tmpfolder.join("a-dir/a-file.txt").check()
    # When it is moved with pretend kwarg,
    utils.move("another-file.txt", target="a-dir", pretend=True)
    # Then the src should not be moved
    assert not tmpfolder.join("a-dir/another-file.txt").check()
    assert tmpfolder.join("another-file.txt").check()


def test_get_id():
    def custom_action(structure, options):
        return structure, options

    custom_action.__module__ = "awesome_module"
    assert utils.get_id(custom_action) == "awesome_module:custom_action"


def test_is_dep_included():
    deps = {"setuptools_scm": "some.version", "pyscaffold": "42.0", "django": "0"}
    assert utils.is_dep_included("setuptools_scm>=34", deps)
    assert utils.is_dep_included("pyscaffold>=5.34.5,<=42", deps)
    assert utils.is_dep_included("django", deps)
    assert not utils.is_dep_included("appdirs==1", deps)
    assert not utils.is_dep_included("cookiecutter<8", deps)
    assert not utils.is_dep_included("mypkg~=9.0", deps)


def test_split_deps():
    assert utils.split_deps(
        "\n    pyscaffold>=42.1.0,<43.0"
        "\n    appdirs==1"
        "\n    cookiecutter<8"
        "\n    mypkg~=9.0"
    ) == ["pyscaffold>=42.1.0,<43.0", "appdirs==1", "cookiecutter<8", "mypkg~=9.0"]
    assert utils.split_deps(
        "\n    pyscaffold>=42.1.0,<43.0;appdirs==1"
        "\n    cookiecutter<8;mypkg~=9.0\n\n"
    ) == ["pyscaffold>=42.1.0,<43.0", "appdirs==1", "cookiecutter<8", "mypkg~=9.0"]
    assert utils.split_deps(
        "pyscaffold>=42.1.0,<43.0; appdirs==1; cookiecutter<8; mypkg~=9.0; "
    ) == ["pyscaffold>=42.1.0,<43.0", "appdirs==1", "cookiecutter<8", "mypkg~=9.0"]


def test_remove_deps():
    assert utils.remove_deps(
        ["pyscaffold>=42.1.0,<43.0", "appdirs==1", "cookiecutter<8", "mypkg~=9.0"],
        ["appdirs"],
    ) == ["pyscaffold>=42.1.0,<43.0", "cookiecutter<8", "mypkg~=9.0"]
    assert utils.remove_deps(
        ["pyscaffold>=42.1.0,<43.0", "appdirs==1", "cookiecutter<8", "mypkg~=9.0"],
        {"mypkg": 0},
    ) == ["pyscaffold>=42.1.0,<43.0", "appdirs==1", "cookiecutter<8"]


def test_get_requirements_str():
    own_deps = {
        "setuptools_scm": parse_version("1.2.5"),
        "pyscaffold": parse_version("42.1.0"),
        "django": parse_version("5.3.99999"),
    }
    # No intersection
    assert utils.get_requirements_str(
        ["appdirs==1", "cookiecutter<8", "mypkg~=9.0"], own_deps
    ) == (
        "\n    setuptools_scm>=1.2.5,<2.0"
        "\n    pyscaffold>=42.1.0,<43.0"
        "\n    django>=5.3.99999,<6.0"
        "\n    appdirs==1"
        "\n    cookiecutter<8"
        "\n    mypkg~=9.0"
    )
    # With intersection => own_deps win
    assert utils.get_requirements_str(
        ["appdirs==1", "pyscaffold<8", "mypkg~=9.0"], own_deps
    ) == (
        "\n    setuptools_scm>=1.2.5,<2.0"
        "\n    pyscaffold>=42.1.0,<43.0"
        "\n    django>=5.3.99999,<6.0"
        "\n    appdirs==1"
        "\n    mypkg~=9.0"
    )
