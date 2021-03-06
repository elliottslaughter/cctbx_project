from __future__ import division
import iotbx
from cctbx import maptbx
from libtbx.test_utils import approx_equal
from libtbx.utils import format_cpu_times
import libtbx.load_env
from cStringIO import StringIO
import sys

def exercise_with_tst_input_map():
  file_name = libtbx.env.under_dist(
    module_name="iotbx",
    path="ccp4_map/tst_input.map")
  m = iotbx.ccp4_map.map_reader(file_name=file_name)
  assert approx_equal(m.header_min, -0.422722190619)
  assert approx_equal(m.header_max, 0.335603952408)
  assert approx_equal(m.header_mean, 0)
  assert approx_equal(m.header_rms, 0.140116646886)
  assert m.unit_cell_grid == (16, 8, 16)
  assert approx_equal(m.unit_cell_parameters, (
    82.095001220703125, 37.453998565673828, 69.636001586914062,
    90.0, 101.47599792480469, 90.0))
  assert m.space_group_number == 5
  assert m.data.origin() == (0, 0, 0)
  assert m.data.all() == (16, 8, 16)
  assert not m.data.is_padded()
  out = StringIO()
  m.show_summary(out=out)
  assert ("map grid:   (16, 8, 16)" in out.getvalue())
  uc = m.unit_cell()
  assert approx_equal(m.unit_cell_parameters, m.unit_cell().parameters())
  assert approx_equal(m.grid_unit_cell().parameters(),
    (5.13094, 4.68175, 4.35225, 90, 101.476, 90))

def exercise_crystal_symmetry_from_ccp4_map():
  from iotbx.ccp4_map import crystal_symmetry_from_ccp4_map
  file_name = libtbx.env.under_dist(
    module_name="iotbx",
    path="ccp4_map/tst_input.map")
  cs = crystal_symmetry_from_ccp4_map.extract_from(file_name=file_name)

def exercise(args):
  exercise_with_tst_input_map()
  for file_name in args:
    print file_name
    m = iotbx.ccp4_map.map_reader(file_name=file_name)
    print "header_min: ", m.header_min
    print "header_max: ", m.header_max
    print "header_mean:", m.header_mean
    print "header_rms: ", m.header_rms
    print "unit cell grid:", m.unit_cell_grid
    print "unit cell parameters:", m.unit_cell_parameters
    print "space group number:  ", m.space_group_number
    print "map origin:", m.data.origin()
    print "map grid:  ", m.data.all()
    map_stats = maptbx.statistics(m.data)
    assert approx_equal(map_stats.min(), m.header_min)
    assert approx_equal(map_stats.max(), m.header_max)
    assert approx_equal(map_stats.mean(), m.header_mean)
    if (m.header_rms != 0):
      assert approx_equal(map_stats.sigma(), m.header_rms)
    print

def exercise_writer () :
  from cctbx import uctbx, sgtbx
  from scitbx.array_family import flex
  mt = flex.mersenne_twister(0)
  nxyz = (4,4,4,)
  grid = flex.grid(nxyz)
  real_map_data = mt.random_double(size=grid.size_1d())
  real_map_data.reshape(grid)
  unit_cell=uctbx.unit_cell((10,10,10,90,90,90))
  iotbx.ccp4_map.write_ccp4_map(
      file_name="four_by_four.map",
      unit_cell=unit_cell,
      space_group=sgtbx.space_group_info("P1").group(),
      map_data=real_map_data,
      labels=flex.std_string(["iotbx.ccp4_map.tst"]))
  input_real_map = iotbx.ccp4_map.map_reader(file_name="four_by_four.map")
  input_map_data=input_real_map.map_data()
  real_map_mmm = real_map_data.as_1d().min_max_mean()
  input_map_mmm = input_map_data.as_1d().min_max_mean()
  cc=flex.linear_correlation(real_map_data.as_1d(),input_map_data.as_1d()).coefficient()
  assert cc > 0.999

  assert approx_equal(input_real_map.unit_cell_parameters,
                      unit_cell.parameters())
  assert approx_equal(real_map_mmm.min, input_real_map.header_min,eps=0.001)
  assert approx_equal(real_map_mmm.min, input_map_mmm.min,eps=0.001)


  # random small maps of different sizes
  for nxyz in flex.nested_loop((2,1,1),(4,4,4)):
    mt = flex.mersenne_twister(0)
    grid = flex.grid(nxyz)
    real_map = mt.random_double(size=grid.size_1d())
    real_map=real_map-0.5
    real_map.reshape(grid)
    iotbx.ccp4_map.write_ccp4_map(
      file_name="random.map",
      unit_cell=uctbx.unit_cell((1,1,1,90,90,90)),
      space_group=sgtbx.space_group_info("P1").group(),
      gridding_first=(0,0,0),
      gridding_last=tuple(grid.last(False)),
      map_data=real_map,
      labels=flex.std_string(["iotbx.ccp4_map.tst"]))
    m = iotbx.ccp4_map.map_reader(file_name="random.map")
    mmm = flex.double(list(real_map)).min_max_mean()
    m1=real_map.as_1d()
    m2=m.map_data().as_1d()
    cc=flex.linear_correlation(m1,m2).coefficient()
    assert cc > 0.999
    assert approx_equal(m.unit_cell_parameters, (1,1,1,90,90,90))
    assert approx_equal(mmm.min, m.header_min)
    assert approx_equal(mmm.max, m.header_max)
    #
    # write unit_cell_grid explicitly to map
    iotbx.ccp4_map.write_ccp4_map(
      file_name="random_b.map",
      unit_cell=uctbx.unit_cell((1,1,1,90,90,90)),
      space_group=sgtbx.space_group_info("P1").group(),
      unit_cell_grid=real_map.all(),
      map_data=real_map,
      labels=flex.std_string(["iotbx.ccp4_map.tst"]))
    m = iotbx.ccp4_map.map_reader(file_name="random_b.map")
    m1=real_map.as_1d()
    m2=m.map_data().as_1d()
    cc=flex.linear_correlation(m1,m2).coefficient()
    assert cc > 0.999

    mmm = flex.double(list(real_map)).min_max_mean()
    assert approx_equal(m.unit_cell_parameters, (1,1,1,90,90,90))
    assert approx_equal(mmm.min, m.header_min)
    assert approx_equal(mmm.max, m.header_max)
    #

    #
    gridding_first = (0,0,0)
    gridding_last=tuple(grid.last(False))
    map_box = maptbx.copy(real_map, gridding_first, gridding_last)
    map_box.reshape(flex.grid(map_box.all()))
    iotbx.ccp4_map.write_ccp4_map(
      file_name="random_box.map",
      unit_cell=uctbx.unit_cell((1,1,1,90,90,90)),
      space_group=sgtbx.space_group_info("P1").group(),
      map_data=map_box,
      labels=flex.std_string(["iotbx.ccp4_map.tst"]))
  print "OK"

def run(args):
  import iotbx.ccp4_map
  exercise(args=args)
  exercise_writer()
  exercise_crystal_symmetry_from_ccp4_map()
  print format_cpu_times()

if (__name__ == "__main__"):
  run(sys.argv[1:])
