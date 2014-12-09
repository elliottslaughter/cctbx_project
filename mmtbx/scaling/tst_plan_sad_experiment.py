
from __future__ import division
from mmtbx.command_line import plan_sad_experiment
from libtbx.test_utils import approx_equal, Exception_expected
from libtbx.utils import null_out, Sorry

def exercise () :
  # Generic SeMet protein (actually Rv0577)
  args = [
    "resolution=2.2",
    "atom_type=Se",
    "residues=300",
    "wavelength=0.9794",
    "include_weak_anomalous_scattering=False",
    "sites=12",
  ]
  result = plan_sad_experiment.run(args=args, out=null_out()).show(null_out())
  assert approx_equal(result.representative_values[:-1],
   [2.5, 12, 10880.374304954881, 3.8438000679016113, 97.77777777777779, 0.009, 0.633223687444356, 0.8462116413131916, 0.6405243342470512, 0.7180836137391196, 23.365672552879058, 94.95498749053407], eps=0.01)
  assert (93 < result.representative_values[-2] < 97)
  # Insulin S-SAD
  open("tst_plan_sad_experiment.fa", "w").write("""
>1ZNI:A|PDBID|CHAIN|SEQUENCE
GIVEQCCTSICSLYQLENYCN
>1ZNI:B|PDBID|CHAIN|SEQUENCE
FVNQHLCGSHLVEALYLVCGERGFFYTPKA
>1ZNI:C|PDBID|CHAIN|SEQUENCE
GIVEQCCTSICSLYQLENYCN
>1ZNI:D|PDBID|CHAIN|SEQUENCE
FVNQHLCGSHLVEALYLVCGERGFFYTPKA
""")
  args = [
    "seq_file=tst_plan_sad_experiment.fa",
    "atom_type=S",
    "resolution=1.2",
    "wavelength=1.54"
  ]
  result = plan_sad_experiment.run(args=args, out=null_out())
  assert approx_equal(result.representative_values[:-1],
  [2, 12, 7225.2485618841, 0.5562999844551086, 97.77777777777779, 0.009, 0.3264043803898403, 0.6106881338839417, 0.5635269556200062, 0.6531008851070139, 11.117707953181952, 81.41197783613683], eps=0.01)
  assert (79 < result.representative_values[-2] < 83)
  # now with worse resolution
  args = [
    "seq_file=tst_plan_sad_experiment.fa",
    "atom_type=S",
    "resolution=3.0",
    "wavelength=1.54"
  ]
  result = plan_sad_experiment.run(args=args, out=null_out())
  assert approx_equal(result.representative_values[:-1],
  [5, 12, 462.41590796058244, 0.5562999844551086, 97.77777777777779, 0.009, 0.44571173471146186, 0.6638663305757504, 0.6056932839550113, 0.6699731002798963, 4.8691231380721245, 16.41105412132456], eps=0.01)

  # Error handling
  args = [
    "resolution=2.2",
    "atom_type=Se",
    "wavelength=0.9794",
    "sites=12",
  ]
  try :
    result = plan_sad_experiment.run(args=args, out=null_out())
  except Sorry :
    pass
  else :
    raise Exception_expected

if (__name__ == "__main__") :
  exercise()
  print "OK"
