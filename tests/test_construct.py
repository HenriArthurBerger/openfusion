"""Construction planes and axes: reference bodies that work wherever an anchor does."""
import numpy as np
import pytest

from openfusion import Engine, export, topo

ENGINE = Engine()
BLOCK = "from openfusion import *\nblock = box(length=40, width=20, height=10)\n"


def run(src):
    return ENGINE.run_source(BLOCK + src)


def frame(r, name):
    return r.bodies[name].anchor("origin")


def status(r, name):
    res = next(x for x in r.results if x.name == name)
    return res.status, res.message


def test_planes_offset_tilted_mid_and_through_points():
    r = run('p1 = plane(block.face("+Z"), offset=5)\n'
            'p2 = plane(mid=(block.face("-X"), block.face("+X")))\n'
            'p3 = plane(block.face("+Z"), angle=30, about=block.edge("+Y+Z"))\n'
            'p4 = plane(points=(block.anchor("+++"), block.anchor("-++"), block.anchor("+-+")))\n'
            'p5 = plane(block.face("+Z"), angle=90, about="Y", size=12)\n'
            'p6 = plane(angle=45, about=block.edge("+X+Y"))\n'
            'p7 = plane()\n')
    assert all(x.status == "ok" for x in r.results), r.report()
    f = frame(r, "p1")
    assert np.allclose(f.origin, (20, 10, 15)) and np.allclose(f.z, (0, 0, 1))
    f = frame(r, "p2")
    assert np.allclose(f.origin, (20, 10, 5)) and abs(f.z[0]) == pytest.approx(1)
    f = frame(r, "p3")
    assert np.allclose(f.origin[1:], (20, 10)) and np.allclose(f.z, (0, -0.5, np.sqrt(3) / 2))
    assert abs(frame(r, "p4").z[2]) == pytest.approx(1) and frame(r, "p4").origin[2] == pytest.approx(10)
    assert np.allclose(frame(r, "p5").z, (1, 0, 0), atol=1e-9)
    lo, hi = topo.bbox(r.bodies["p5"].shape)
    assert (hi - lo).max() == pytest.approx(12)
    b = r.bodies["p1"]
    assert b.kind == "construction" and b.role == "reference" and export.printable([b]) == []
    z6 = frame(r, "p6").z                      # turned 45 degrees about the vertical edge, from its flat face
    assert abs(z6[0]) == pytest.approx(np.sqrt(0.5)) and abs(z6[1]) == pytest.approx(np.sqrt(0.5)) and z6[2] == pytest.approx(0)


def test_planes_and_axes_feed_other_steps():
    r = run('p = plane(block.face("+Z"), offset=5)\n'
            'c = cylinder(r=2, h=5, at=p)\n'
            'mid = plane(mid=(block.face("-X"), block.face("+X")))\n'
            'right = split(block, plane=mid)\n'
            's = sketch(at=plane(block.face("+Y"), angle=20, about="X"), points={"o": (0, 0)}, curves={"c": ("circle", "o", 2)})\n'
            'a = axis(block.edge("+X+Y"))\n'
            'pin = cylinder(r=1, h=3, at=world.point(60, 0, 0))\n'
            'ring = pattern_circ(pin, 4, axis=a)\n'
            'turn = rotate(pin, 30, about=axis(points=(block.anchor("+++"), block.anchor("---"))))\n')
    assert all(x.status == "ok" for x in r.results), r.report()
    assert frame(r, "c").origin[2] == pytest.approx(15)
    lo, hi = topo.bbox(r.bodies["block"].shape)
    assert 20 in (pytest.approx(lo[0]), pytest.approx(hi[0]))      # split at the midplane


def test_axes_from_edges_faces_anchors_and_points():
    r = run('a1 = axis(block.edge("+X+Y"))\n'
            'c = cylinder(r=3, h=8, at=world.point(80, 0, 0))\n'
            'a2 = axis(c.face("side"), length=30)\n'
            'a3 = axis(block.anchor("+Z"))\n'
            'a4 = axis(points=(block.anchor("---"), block.anchor("+++")))\n')
    assert all(x.status == "ok" for x in r.results), r.report()
    assert np.allclose(frame(r, "a1").z, (0, 0, 1)) and np.allclose(frame(r, "a1").origin[:2], (40, 20))
    assert topo.edge_length(topo.edges(r.bodies["a1"].shape)[0]) == pytest.approx(10)
    assert np.allclose(frame(r, "a2").origin[:2], (80, 0)) and topo.edge_length(topo.edges(r.bodies["a2"].shape)[0]) == pytest.approx(30)
    assert np.allclose(frame(r, "a3").z, (0, 0, 1))
    a4 = r.bodies["a4"]
    assert np.allclose(a4.anchor("end").origin, (40, 20, 10)) and np.allclose(a4.anchor("start").origin, (0, 0, 0))


def test_construction_errors():
    assert "give one of" in status(run('p = plane(mid=(block.face("-X"), block.face("+X")), points=(1, 2, 3))\n'), "p")[1]
    assert "three points" in status(run('p = plane(points=(block.anchor("+++"),))\n'), "p")[1]
    assert "in a line" in status(run('p = plane(points=(block.anchor("---"), block.anchor("center"), block.anchor("+++")))\n'), "p")[1]
    assert "two faces" in status(run('p = plane(mid=(block.face("-X"),))\n'), "p")[1]
    assert "aren't parallel" in status(run('p = plane(mid=(block.face("-X"), block.face("+Z")))\n'), "p")[1]
    assert "'X', 'Y'" in status(run('p = plane(block.face("+Z"), about="Z")\n'), "p")[1]
    assert "along the plane's normal" in status(run('p = plane(block.face("+Z"), about=block.edge("+X+Y"))\n'), "p")[1]
    assert "size must be positive" in status(run('p = plane(size=-1)\n'), "p")[1]
    assert "give an edge" in status(run('a = axis()\n'), "a")[1]
    assert "two points" in status(run('a = axis(points=(block.anchor("+++"),))\n'), "a")[1]
    assert "the same" in status(run('a = axis(points=(block.anchor("+++"), block.anchor("+++")))\n'), "a")[1]
    assert "length must be positive" in status(run('a = axis(block.anchor("+Z"), length=0)\n'), "a")[1]


def test_tangent_planes_touch_round_faces():
    import numpy as np
    from openfusion import Engine, topo
    r = Engine().run_source('''from openfusion import *
shaft = cylinder(r=10, h=30)
t1 = plane(tangent=shaft.face("side"))
t2 = plane(tangent=shaft.face("side"), angle=90)
t3 = plane(tangent=shaft.face("side"), at=world.point(0, 50, 15), offset=2)
s = sketch(at=t3.anchor("origin"), points={"o": (0, 0)}, curves={"c": ("circle", "o", 2)})
c = extrude(s, 5, op="cut", target=shaft)
ball = sphere(r=5, at=world.point(50, 0, 0))
t4 = plane(tangent=ball.face("surface"), at=world.point(60, 10, 0))
box1 = box(length=5, width=5, height=5, at=world.point(0, -50, 0))
t5 = plane(tangent=box1.face("+Z"))
''')
    assert all(x.status == "ok" for x in r.results), r.report()
    o = lambda n: r.bodies[n].anchor("origin")                          # noqa: E731
    t1 = o("t1")
    assert np.hypot(*t1.origin[:2]) == __import__("pytest").approx(10) and abs(float(np.dot(t1.z, [0, 0, 1]))) < 1e-9
    assert np.allclose(t1.x, [0, 0, 1])                                   # X along the axis
    ang = lambda f: np.degrees(np.arctan2(f.origin[1], f.origin[0]))     # noqa: E731
    assert (ang(o("t2")) - ang(t1)) % 360 == __import__("pytest").approx(90)
    assert np.allclose(o("t3").origin, [0, 12, 15]) and np.allclose(o("t3").z, [0, 1, 0])
    assert np.allclose(o("t4").z, [2 ** -0.5, 2 ** -0.5, 0])
    assert np.allclose(o("t5").z, [0, 0, 1]) and o("t5").origin[2] == __import__("pytest").approx(5)
    # the sketch on t3 (2 mm off the shaft) cut 3 mm into it
    assert topo.volume(r.bodies["shaft"].shape) < np.pi * 100 * 30 - 30
    bad = Engine().run_source('from openfusion import *\nb = box(length=5, width=5, height=5)\np = plane(tangent=b.face("+Z"), angle=10)\n')
    assert "no axis" in bad.results[-1].message
