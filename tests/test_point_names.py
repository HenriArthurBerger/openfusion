"""Face points by name: a picked point keeps its name whatever later steps add to the face,
and a name that is gone is an error, never another point. Plus saving when the folder
won't take the file."""
import builtins
import collections
import pathlib

import numpy as np
import pytest

from openfusion import Engine, scriptedit as se, topo
from openfusion.export import scene
from openfusion.gui.server import Session, route
from openfusion.refs import face_anchor_frame, face_points

ENGINE = Engine()
HOLE = ('from openfusion import *\n'
        'body1 = box(length=60, width=40, height=10)\n'
        'body2 = cylinder(r=8, h=10, at=world.point(0, 20, 0))\n'
        'cut1 = cut(target=body1, tools=[body2])\n')
FILLET = 'fillet1 = fillet(body=body1, edges=[body1.edge("+X+Y")], r=6)\n'

# the tester's part (moves, a pattern, chamfers, joins and cuts on one spot)
IPAD = '''from openfusion import *
body1 = box(length=200, width=7.6, height=20, at=world.anchor("XY").offset(x=20))
fillet1 = fillet(body=body1, edges=[body1.edge("+Y-Z")], r=6)
body2 = box(length=12, width=120, height=20, at=world.anchor("XY").offset(x=100))
pattern_rect1 = pattern_rect(body=body2, x=(2, 10))
move1 = move(body=body2)
move2 = move(body=body2, rz=-25, pivot=body2.face("+Z").corner(1))
move3 = move(body=pattern_rect1[1], rz=25, pivot=pattern_rect1[1].face("+Z").corner(2))
move4 = move(body=body1, dy=18, dz=8, rx=-15, pivot=body1.face("+X").corner(3))
extrude1 = extrude(face=pattern_rect1[1].face("-Y"), distance=5)
extrude2 = extrude(face=body2.face("-Y"), distance=5)
move5 = move(body=pattern_rect1[1], frame="world")
chamfer1 = chamfer(body=body2, edges=[body2.edge("+X+Y")], d=5.6, d2=12)
chamfer2 = chamfer(body=pattern_rect1[1], edges=[pattern_rect1[1].edge("-X+Y")], d=12, d2=5.6)
move6 = move(body=pattern_rect1[1], to=body2.face("+X").corner(0), point=pattern_rect1[1].face("-X").corner(1))
body3 = cylinder(r=10, h=-10, at=pattern_rect1[1].face("+Z").corner(3))
body4 = cylinder(r=10, h=-10, at=body2.face("-Z").corner(0))
join1 = join(target=body3, tools=[pattern_rect1[1]])
join2 = join(target=body2, tools=[body4])
body5 = cylinder(r=10, h=-10, at=body2.face("body4.-Z").arc(0), spin=-139.399)
cut1 = cut(target=body3, tools=[body5])
body6 = cylinder(r=10, h=-10, at=body2.face("+Z").corner(0))
cut2 = cut(target=body2, tools=[body6])
body7 = cylinder(r=6, h=-20, at=body3.face("pattern_rect1_1.+Z").arc(0), spin=21.801)
cut3 = cut(target=body3, tools=[body7], keep_tools=True)
'''


def where(r, name):
    return np.round(r.bodies[name].anchor("origin").origin, 6).tolist()


def ok(src):
    r = ENGINE.run_source(src)
    assert r.ok, r.report()
    return r


def test_a_fillet_added_before_a_named_point_leaves_it_where_it_was():
    # the tester's bug: a pin on the notch's arc centre, then a fillet on a corner added earlier
    # in the timeline. By number, arc(0) became the fillet's arc and the pin jumped there.
    pin_n = 'pin = cylinder(r=2, h=5, at=body1.face("+Z").arc(0))\n'
    pin_s = 'pin = cylinder(r=2, h=5, at=body1.face("+Z").arc("body2.side#0"))\n'
    assert where(ok(HOLE + pin_n), "pin") == [0, 20, 10]
    assert where(ok(HOLE + FILLET + pin_n), "pin") == [54, 34, 10]       # (why numbers are a trap)
    for extra in ("", FILLET, FILLET.replace("+X+Y", "-X+Y"), FILLET.replace("+X+Y", "+X-Y")):
        assert where(ok(HOLE + extra + pin_s), "pin") == [0, 20, 10], extra


def test_corner_names_come_from_the_faces_either_side():
    r = ok('from openfusion import *\nb = box(length=60, width=40, height=10)\n' + FILLET.replace("body1", "b")
           + 'p = sphere(r=1, at=b.face("+Z").corner("-X+Y"))\n'
           + 'q = sphere(r=1, at=b.face("+Z").corner("+X|fillet1(+X+Y)"))\n'
           + 'm = sphere(r=1, at=b.face("+Z").mid("fillet1(+X+Y)"))\n'
           + 'a = sphere(r=1, at=b.face("+Z").arc("fillet1(+X+Y)"))\n')
    assert where(r, "p") == [0, 40, 10]
    assert where(r, "q") == [60, 34, 10]
    assert where(r, "a") == [54, 34, 10]
    assert np.allclose(where(r, "m"), [54 + 6 * 0.5 ** 0.5, 34 + 6 * 0.5 ** 0.5, 10], atol=1e-5)


def test_a_point_whose_name_is_gone_is_an_error_not_another_point():
    r = ENGINE.run_source('from openfusion import *\nb = box(length=60, width=40, height=10)\n' + FILLET.replace("body1", "b")
                          + 'p = sphere(r=1, at=b.face("+Z").corner("+X+Y"))\n')
    res = next(x for x in r.results if x.name == "p")
    assert res.status == "error"
    assert 'no corner named "+X+Y"' in res.message and '"+X|fillet1(+X+Y)"' in res.message
    assert "p" not in r.bodies


def test_every_face_point_has_its_own_name_and_finds_itself_again():
    for src in (HOLE + FILLET, IPAD):
        r = ok(src)
        sc = scene(r, None)
        for b in sc["bodies"]:
            seen = collections.defaultdict(set)
            for f in b["faces"]:
                for s in f["snaps"]:
                    seen[s["ref"]].add(tuple(np.round(s["o"], 4)))
                    assert not s["ref"].endswith(("(0)", "(1)", "(2)")), s["ref"]   # never a number
            dup = {k: v for k, v in seen.items() if len(v) > 1}
            assert not dup, dup
        # each named point, used in a step, lands on itself
        body = r.bodies["body3" if src == IPAD else "body1"]
        lines = []
        for f in topo.faces(body.shape):
            if topo.surface_kind(f) != "plane":
                continue
            label = body.label_of(f)
            pts = face_points(body, f, face_anchor_frame(body, [f], None))
            for kind, items in pts["named"].items():
                for nm, p in items:
                    lines.append((f'{body.id}.face({label!r}).{kind}({nm!r})', p))
        probe = src + "".join(f"probe{i} = sphere(r=0.1, at={ref})\n" for i, (ref, _) in enumerate(lines))
        rp = ok(probe)
        for i, (ref, p) in enumerate(lines):
            assert np.allclose(rp.bodies[f"probe{i}"].anchor("origin").origin, p, atol=1e-6), ref


def test_naming_the_numbered_points_keeps_the_part_exactly_as_it_was():
    r = ok(IPAD)
    table = {x.name: x.info["point_names"] for x in r.results if x.info.get("point_names")}
    text, n = se.name_points(IPAD, table)
    assert n == 10
    assert ".corner(" in text and not any(f".{k}({d})" in text for k in ("corner", "arc") for d in range(5))
    assert 'pattern_rect1[1].face("+Z").corner("chamfer2(-X+Y)|-X")' in text      # the expression stays as written
    assert 'body2.face("body4.-Z").arc("body4.side#0")' in text
    r2 = ok(text)
    for k, b in r.bodies.items():
        assert abs(topo.volume(b.shape) - topo.volume(r2.bodies[k].shape)) < 1e-6, k
        assert np.allclose(b.anchor("origin").origin, r2.bodies[k].anchor("origin").origin), k
    assert not any(x.info.get("point_names") for x in r2.results)


# ----------------------------------------------------------------- the app
@pytest.fixture
def hole_sess(tmp_path):
    f = tmp_path / "part.ofs"
    f.write_text(HOLE + 'pin = cylinder(r=2, h=5, at=body1.face("+Z").arc(0))\n')
    s = Session(str(f))
    s.recovery_dir = str(tmp_path / "unsaved")
    return s


def test_the_app_offers_to_name_numbered_points_and_does_it_in_one_undo_step(hole_sess):
    s = hole_sess
    assert s.state()["numbered_points"] == ['body1.face("+Z").arc(0)']
    out = route(s, "/api/name_points", {})
    assert out["changed"] == 1 and out["state"]["numbered_points"] == []
    assert 'at=body1.face("+Z").arc("body2.side#0"))' in pathlib.Path(s.path).read_text()
    assert out["state"]["undo"] == "name the picked points"
    route(s, "/api/apply", {"op": "fillet", "args": {"body": "body1", "edges": '[body1.edge("+X+Y")]', "r": "6"}, "name": "f1"})
    # the fillet went in after the pin; move it before: the pin stays on the notch
    route(s, "/api/move", {"name": "f1", "after": "cut1"})
    assert where(s.result, "pin") == [0, 20, 10]


def test_a_folder_that_refuses_a_new_file_still_saves_into_the_file(hole_sess, monkeypatch):
    # macOS lets an app handed one file write that file but create nothing beside it
    s = hole_sess
    real = pathlib.Path.write_text

    def no_tmp(self, *a, **k):
        if str(self).endswith(".tmp"):
            raise PermissionError(1, "Operation not permitted", str(self))
        return real(self, *a, **k)
    monkeypatch.setattr(pathlib.Path, "write_text", no_tmp)
    route(s, "/api/apply", {"op": "sphere", "args": {"r": "3"}})
    assert "sphere(r=3)" in pathlib.Path(s.path).read_text()
    assert s.save_error is None and not pathlib.Path(s.path + ".tmp").exists()


def test_a_file_that_cannot_be_written_keeps_the_change_and_says_why(hole_sess, monkeypatch):
    s = hole_sess
    before = pathlib.Path(s.path).read_text()
    real_open, real_wt = builtins.open, pathlib.Path.write_text

    def deny(path):
        return str(path).startswith(s.path)

    def fake_open(file, mode="r", *a, **k):
        if deny(file) and any(c in mode for c in "wa+"):
            raise PermissionError(1, "Operation not permitted", str(file))
        return real_open(file, mode, *a, **k)

    def fake_wt(self, *a, **k):
        if deny(self):
            raise PermissionError(1, "Operation not permitted", str(self))
        return real_wt(self, *a, **k)
    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(pathlib.Path, "write_text", fake_wt)
    out = route(s, "/api/apply", {"op": "sphere", "args": {"r": "3"}})          # no internal error
    st = out["state"]
    assert "sphere(r=3)" in st["text"] and "body3" in [b["id"] for b in st["scene"]["bodies"]]
    assert st["save_error"].startswith("Not saved to part.ofs: macOS didn't let OpenFusion write")
    assert "Save a Copy As" in st["save_error"]
    copy = pathlib.Path(s.recovery_dir) / "part.ofs"
    assert copy.read_text() == s.text and str(copy) in st["save_error"]
    assert pathlib.Path(s.path).read_text() == before
    assert s.check_disk() is False and "sphere(r=3)" in s.text        # the old file doesn't win
    route(s, "/api/undo", {})
    assert "sphere(r=3)" not in s.text
    monkeypatch.undo()
    route(s, "/api/redo", {})                                         # writable again: saved, banner gone
    assert "sphere(r=3)" in pathlib.Path(s.path).read_text() and s.state()["save_error"] is None
