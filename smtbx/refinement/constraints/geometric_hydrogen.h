#ifndef SMTBX_REFINEMENT_CONSTRAINTS_GEOMETRIC_HYDROGEN_H
#define SMTBX_REFINEMENT_CONSTRAINTS_GEOMETRIC_HYDROGEN_H

#include <scitbx/constants.h>
#include <scitbx/array_family/tiny.h>
#include <scitbx/array_family/shared.h>
#include <scitbx/array_family/simple_tiny_io.h>

#include <cctbx/coordinates.h>

#include <smtbx/refinement/parameter_map.h>
#include <smtbx/import_scitbx_af.h>
#include <smtbx/import_cctbx.h>

namespace smtbx { namespace refinement { namespace constraints {

namespace constants {
  using namespace scitbx::constants;
  static double const tetrahedral_angle = std::acos(-1./3.);
  static double const sin_tetrahedral_angle = std::sin(tetrahedral_angle);
}

/// Base class for all geometrically constrained hydrogen's -XHn
/** It uses the curiously recurring template pattern (CRTP) to achieve
    polymorphism resolved at compile time. It is also a lightweight pattern,
    i.e. the information needed by its member functions which is shared by
    many instances, such as unit cell, site symmetry, etc, is not part of the
    state. Instead it is passed as arguments to those member functions.

*/
template<class DerivedType,
         typename FloatType, class XrayScattererType,
         template<class, std::size_t> class HydrogenArrayTemplate, int NHydrogens,
         template<class> class SharedArray1D=af::shared>
class geometrical_hydrogens
{
  public:
    typedef XrayScattererType xray_scatterer_type;
    typedef FloatType float_type;
    typedef parameter_map<xray_scatterer_type> parameter_map_type;
    typedef cartesian<float_type> cart_t;
    typedef fractional<float_type> frac_t;
    typedef HydrogenArrayTemplate<int, NHydrogens> hydrogen_index_array_type;
    typedef HydrogenArrayTemplate<cart_t, NHydrogens> hydrogen_grad_array_type;

    /// Construct a constraint for the scatterers with the given indices
    /// in the array to be passed to the other member functions.
    geometrical_hydrogens(int pivot,
                          hydrogen_index_array_type hydrogens,
                          float_type bond_length,
                          bool stretching=false
                          )
      : on_(true),
        i_pivot(pivot),
        i_hydrogens(hydrogens),
        stretching_(stretching),
        l(bond_length)
    {}

    /// Convenience constructor for the configuration with only 1 hydrogen
    geometrical_hydrogens(int pivot,
                          int hydrogen,
                          float_type bond_length,
                          bool stretching=false
                          )
      : on_(true),
        i_pivot(pivot),
        i_hydrogens(hydrogen),
        stretching_(stretching),
        l(bond_length)
    {}

    int pivot() { return i_pivot; }

    hydrogen_index_array_type hydrogens() { return i_hydrogens; }

    bool stretching() { return stretching_; }
    void set_stretching(bool f) { stretching_ = f; }

    float_type bond_length() { return l; }
    void set_bond_length(float_type l_) { l = l_; }

    /// Initialise the constraint for the given context.
    void initialise_in_context(
      uctbx::unit_cell const &unit_cell,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::const_ref<xray_scatterer_type> const &scatterers,
      af::ref<xray::scatterer_flags> const &constraint_flags,
      std::map<int, xray::scatterer_flags> &already_constrained)
    {
      for(int i=0; i < i_hydrogens.size(); ++i) {
        int i_h = i_hydrogens[i];
        xray::scatterer_flags f = constraint_flags[i_h];
        if (!f.grad_site()) {
          already_constrained[i_h] = f;
          on_ = false;
        }
        constraint_flags[i_hydrogens[i]].set_grad_site(false);
      }
      if (!on_) return;
      heir().do_initialise_in_context(unit_cell,
                                      site_symmetry_table,
                                      scatterers,
                                      constraint_flags,
                                      already_constrained);
    }

    /// Called by initialise_in_context
    /** Heirs may override it if extra computations are needed to initialise
        the constraint
    */
    void do_initialise_in_context(
      uctbx::unit_cell const &unit_cell,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::const_ref<xray_scatterer_type> const &scatterers,
      af::ref<xray::scatterer_flags> const &constraint_flags,
      std::map<int, xray::scatterer_flags> &already_constrained)
    {}

    /// Compute the derivatives of Fc wrt to all parameters.
    /** It always does at least make the Hydrogen ride on the pivot atom.

        \arg crystallographic_gradients On entry, it contains the
        derivatives of Fc wrt the crystallographic parameters. If this
        constraint requires some of those parameters to be function of others,
        it may modify the relevant elements of this array.

        \arg reparametrization_gradients This function must append to this
        array the derivatives wrt to the non-crystallographic parameters that
        this constraint is expressed with.
    */
    void compute_gradients(
      uctbx::unit_cell const &uc,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::const_ref<xray_scatterer_type> const &scatterers,
      parameter_map_type const &crystallographic_parameter_map,
      af::ref<float_type> const &crystallographic_gradients,
      SharedArray1D<float_type> reparametrization_gradients)
    {
      if (!on_) return;

      // Riding
      for(int i=0; i < i_hydrogens.size(); ++i) {
        int i_h = i_hydrogens[i];
        SMTBX_ASSERT(scatterers[i_h].flags.grad_site())(i_h);
        int i_grad_site_pivot = crystallographic_parameter_map[i_pivot].site;
        int i_grad_site_h = crystallographic_parameter_map[i_h].site;
        for(int j=0; j < 3; ++j) {
          crystallographic_gradients[i_grad_site_pivot + j]
            += crystallographic_gradients[i_grad_site_h + j];
        }
      }

      // Reparametrizations
      if (!heir().has_active_reparametrizations()) return;

      i_reparametrization_begin = reparametrization_gradients.size();

      hydrogen_grad_array_type dF_over_dx;
      for (int i=0; i < i_hydrogens.size(); ++i) {
        int i_h = i_hydrogens[i];
        int i_grad_site_h = crystallographic_parameter_map[i_h].site;
        frac_t dF_over_dx_frac(&crystallographic_gradients[i_grad_site_h]);
        dF_over_dx[i] = uc.orthogonalize_gradient(dF_over_dx_frac);
      }

      // Stretching
      if (stretching()) {
        float_type dF_over_dl = 0;
        for (int i=0; i < i_hydrogens.size(); ++i) {
          int i_h = i_hydrogens[i];
          int i_grad_site_h = crystallographic_parameter_map[i_h].site;
          frac_t dF_over_dx_frac(&crystallographic_gradients[i_grad_site_h]);
          cart_t dF_over_dx = uc.orthogonalize_gradient(dF_over_dx_frac);
          dF_over_dl += dF_over_dx * dx_over_dl[i];
        }
        reparametrization_gradients.push_back(dF_over_dl);
      }

      // Other reparametrisations deferred to heirs
      heir().compute_reparametrisation_gradients(uc,
                                                 scatterers,
                                                 dF_over_dx,
                                                 reparametrization_gradients);
    }

    bool has_active_reparametrizations() { return stretching(); }

    /// Called by compute_gradients.
    /** Heirs shall override it if they do more than just riding.
        The arguments have the same meaning as for compute_gradients.
    */
    void compute_reparametrisation_gradients(
      uctbx::unit_cell const &uc,
      af::const_ref<xray_scatterer_type> const &scatterers,
      hydrogen_grad_array_type const &dF_over_dx,
      SharedArray1D<float_type> reparametrization_gradients)
    {}

    /// Apply the given shift to update the scatterers.
    /** \arg crystallographic_shifts Shifts to the parameters of the scatterers
        \arg reparametrization_shifts Shifts to the non-crystallographic
        parameters.
    */
    void apply_shifts(
      uctbx::unit_cell const &unit_cell,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::ref<xray_scatterer_type> const &scatterers,
      parameter_map_type const &crystallographic_parameter_map,
      af::const_ref<float_type> const &crystallographic_shifts,
      af::const_ref<float_type> const &reparametrization_shifts)
    {
      if (!on_) return;
      heir().do_apply_reparametrization_shifts(reparametrization_shifts);
      heir().place_constrained_scatterers(unit_cell,
                                          site_symmetry_table,
                                          scatterers);
    }

    /// Called by apply_shifts
    /** Heirs shall override it to apply the shifts to the non-crystallographic
    parameters they hold, if there are any
    */
    void do_apply_reparametrization_shifts(
      af::const_ref<float_type> const &reparametrization_shifts)
    {}

  protected:
    bool on_;

    int i_pivot;
    hydrogen_index_array_type i_hydrogens;

    bool stretching_;
    float_type l;

    int i_reparametrization_begin;
    hydrogen_grad_array_type dF_over_dx, dx_over_dl;

  private:
    DerivedType &heir() { return static_cast<DerivedType &> (*this); }
};


/// Model of Y-XH3 with tetrahedral angles
/**
  X is referred to as the "pivot" and Y as the "pivot neighbour".

  All angles Hi-X-Hj and Hi-X-Y are tetrahedral.
  All distances X-Hi are equal. That unique distance may be a variable
  parameter if stretching is allowed.
  A free rotation around the bond Y-X is allowed.

  The Hydrogen sites ride on the pivot site.
*/
template<typename FloatType, class XrayScattererType,
         template<class> class SharedArray1D=af::shared>
class terminal_X_Hn
  : public geometrical_hydrogens<terminal_X_Hn<FloatType,
                                               XrayScattererType,
                                               SharedArray1D>,
                                 FloatType, XrayScattererType,
                                 af::small, 3,
                                 SharedArray1D>
{
  public:
    typedef geometrical_hydrogens<terminal_X_Hn<FloatType,
                                                XrayScattererType,
                                                SharedArray1D>,
                                  FloatType, XrayScattererType,
                                  af::small, 3,
                                  SharedArray1D>
            base_t;
    using base_t::i_pivot;
    using base_t::i_hydrogens;
    using base_t::l;
    using base_t::i_reparametrization_begin;
    using base_t::dx_over_dl;

    typedef XrayScattererType xray_scatterer_type;
    typedef FloatType float_type;
    typedef parameter_map<xray_scatterer_type> parameter_map_type;
    typedef cartesian<float_type> cart_t;
    typedef fractional<float_type> frac_t;
    typedef typename base_t::hydrogen_grad_array_type hydrogen_grad_array_type;

    terminal_X_Hn(
      int pivot, int pivot_neighbour,
      af::small<int, 3> hydrogens,
      float_type azimuth_, //degrees
      float_type bond_length,
      bool rotating=true,
      bool stretching=false
      )
      : base_t(pivot, hydrogens, bond_length, stretching),
        i_pivot_neighbour(pivot_neighbour),
        rotating_(rotating),
        phi(azimuth_*constants::pi/180)
    {}

    bool rotating() { return rotating_; }
    void set_rotating(bool f) { rotating_ = f; }

    boost::tuple<cart_t, cart_t, cart_t> local_cartesian_frame() {
      return boost::make_tuple(e0, e1, e2);
    }

    float_type azimuth() { return phi*180/constants::pi; }
    void set_azimuth(float_type phi_) { phi = phi_*constants::pi/180; }

    void do_initialise_in_context(
      uctbx::unit_cell const &unit_cell,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::const_ref<xray_scatterer_type> const &scatterers,
      af::ref<xray::scatterer_flags> const &constraint_flags,
      std::map<int, xray::scatterer_flags> &already_constrained)
    {
      cart_t x_pn = unit_cell.orthogonalize(scatterers[i_pivot_neighbour].site);
      cart_t x_p  = unit_cell.orthogonalize(scatterers[i_pivot].site);
      e2 = (x_p - x_pn).normalize();
      e1 = e2.ortho(true);
      e0 = e1.cross(e2);
    }

    void place_constrained_scatterers(
      uctbx::unit_cell const &unit_cell,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::ref<xray_scatterer_type> const &scatterers)
    {
      using namespace constants;
      /* As the X-Y bond direction changes, we need to update the local frame.
         Our method ensure a smooth rotation whereas
         recomputing e0,e1,e2 as in initialise_in_context may result in
         a sudden jump (c.f. implementation of member function "ortho").
      */
      cart_t x_pn = unit_cell.orthogonalize(scatterers[i_pivot_neighbour].site);
      cart_t x_p  = unit_cell.orthogonalize(scatterers[i_pivot].site);
      cart_t e_bond = x_p - x_pn;
      cart_t f2 = e_bond.normalize();
      e1 = f2.cross(e0);
      e2 = f2;
      e0 = e1.cross(e2);

      // Compute cosines and sines
      af::small<float_type, 3> cos_phi, sin_phi;
      switch (i_hydrogens.size()) {
        case 3:
          cos_phi[2] = std::cos(phi + 4*pi/3);
          sin_phi[2] = std::sin(phi + 4*pi/3);
        case 2:
          cos_phi[1] = std::cos(phi + 2*pi/3);
          sin_phi[1] = std::sin(phi + 2*pi/3);
        case 1:
          cos_phi[0] = std::cos(phi);
          sin_phi[0] = std::sin(phi);
          break;
        default:
          throw std::runtime_error("smtbx: number of geometric hydrogens "
                                   "must be 1,2 or 3");
      }

      // Place hydrogen's
      for (int i=0; i < i_hydrogens.size(); ++i) {
        int i_h = i_hydrogens[i];
        cart_t x_h = x_p
                     + l*(sin_tetrahedral_angle*(cos_phi[i]*e0 + sin_phi[i]*e1)
                          + e2/3);
        scatterers[i_h].site = unit_cell.fractionalize(x_h);
      }

      // Compute derivatives
      for (int i=0; i < i_hydrogens.size(); ++i) {
        if (rotating()) {
          dx_over_dphi[i]
            = l*sin_tetrahedral_angle*(-sin_phi[i]*e0 + cos_phi[i]*e1);
        }
        if (base_t::stretching()) {
          dx_over_dl[i]
            = sin_tetrahedral_angle*(cos_phi[i]*e0 + sin_phi[i]*e1) + e2/3;
        }
      }
    }

    bool has_active_reparametrizations() {
      return base_t::has_active_reparametrizations() || rotating();
    }

    /// Azimuthal rotation
    void compute_reparametrisation_gradients(
      uctbx::unit_cell const &uc,
      af::const_ref<xray_scatterer_type> const &scatterers,
      hydrogen_grad_array_type const &dF_over_dx,
      SharedArray1D<float_type> reparametrization_gradients)
    {
      using namespace constants;
      if (!rotating()) return;
      float_type dF_over_dphi = 0;
      for (int i=0; i < i_hydrogens.size(); ++i) {
        dF_over_dphi += dF_over_dx[i] * dx_over_dphi[i];
      }
      dF_over_dphi *= pi/180;
      reparametrization_gradients.push_back(dF_over_dphi);
    }

    void do_apply_reparametrization_shifts(
      af::const_ref<float_type> const &reparametrization_shifts)
    {
      using namespace constants;

      if (rotating()) {
        int i = i_reparametrization_begin;
        if (base_t::stretching()) i++;
        float_type delta_phi = reparametrization_shifts[i];
        phi += delta_phi;
      }
      if (base_t::stretching()) {
        int i = i_reparametrization_begin;
        float_type delta_l = reparametrization_shifts[i];
        l += delta_l;
      }
    }

  private:
    int i_pivot_neighbour;
    bool rotating_;

    cart_t e0, e1, e2;
    float_type phi;

    af::small<cart_t, 3> dx_over_dphi;
};


/// Model of X-CH2-Y
/**
  C is referred to as the "pivot" and X and Y as pivot's neighbour 1 and 2.

  All angles Hi-C-X and Hi-C-Y are equal.
  The angle H-C-H depends on XY^2 in a simple linear manner as ShelXL does it.
*/
template<typename FloatType, class XrayScattererType,
         template<class> class SharedArray1D=af::shared>
class secondary_CH2
  : public geometrical_hydrogens<secondary_CH2<FloatType,
                                               XrayScattererType,
                                               SharedArray1D>,
                                 FloatType, XrayScattererType,
                                 af::tiny, 2,
                                 SharedArray1D>
{
  public:
    typedef geometrical_hydrogens<secondary_CH2<FloatType,
                                                XrayScattererType,
                                                SharedArray1D>,
                                  FloatType, XrayScattererType,
                                  af::tiny, 2,
                                  SharedArray1D>
            base_t;
    using base_t::i_pivot;
    using base_t::i_hydrogens;
    using base_t::l;
    using base_t::dx_over_dl;

    typedef XrayScattererType xray_scatterer_type;
    typedef FloatType float_type;
    typedef parameter_map<xray_scatterer_type> parameter_map_type;
    typedef cartesian<float_type> cart_t;
    typedef fractional<float_type> frac_t;

    static float_type theta0, dtheta_over_dXY_sq;

    secondary_CH2(int pivot,
                  af::tiny<int, 2> pivot_neighbours,
                  af::tiny<int, 2> hydrogens,
                  float_type bond_length,
                  bool stretching=false)
      : base_t(pivot, hydrogens, bond_length, stretching),
        i_pivot_neighbours(pivot_neighbours)
    {}

    void place_constrained_scatterers(
      uctbx::unit_cell const &uc,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::ref<xray_scatterer_type> const &scatterers)
    {
      /* Recompute local frame: (C,e0,e1) is the bisecting plane
         of the angle X-C-Y with e0 bisecting X-C-Y
      */
      cart_t x_p  = uc.orthogonalize(scatterers[i_pivot].site);
      cart_t x_pn_1 = uc.orthogonalize(scatterers[i_pivot_neighbours[0]].site),
             x_pn_2 = uc.orthogonalize(scatterers[i_pivot_neighbours[1]].site);
      cart_t u_pn_1 = (x_p - x_pn_1).normalize(),
             u_pn_2 = (x_p - x_pn_2).normalize();
      cart_t e0 = (u_pn_1 + u_pn_2).normalize();
      cart_t e2 = (u_pn_2 - u_pn_1).normalize();
      cart_t e1 = e2.cross(e0);

      // Compute cosine and sine
      float_type d_XY_sq = (x_pn_2 - x_pn_1).length_sq();
      float_type theta = theta0 - dtheta_over_dXY_sq*d_XY_sq;
      float_type c = std::cos(theta), s = std::sin(theta);

      // Place hydrogen's
      cart_t site_h_1 = x_p + l*(c*e0 + s*e1);
      cart_t site_h_2 = x_p + l*(c*e0 - s*e1);
      scatterers[i_hydrogens[0]].site = uc.fractionalize(site_h_1);
      scatterers[i_hydrogens[1]].site = uc.fractionalize(site_h_2);

      // Compute derivatives
      dx_over_dl[0] = c*e0 + s*e1;
      dx_over_dl[1] = c*e0 - s*e1;
    }

  private:
    af::tiny<int, 2> i_pivot_neighbours;
};


// Numbers from ShelXL (file xl.f, line 8411)
template<typename FloatType, class XrayScattererType,
         template<class> class SharedArray1D>
FloatType
secondary_CH2<FloatType, XrayScattererType, SharedArray1D>::
theta0 = 1.0376;

template<typename FloatType, class XrayScattererType,
         template<class> class SharedArray1D>
FloatType
secondary_CH2<FloatType, XrayScattererType, SharedArray1D>::
dtheta_over_dXY_sq = -0.0349;


/// Model of tertiary CH
/** All angles Hi-C-X are equal.
*/
template<typename FloatType, class XrayScattererType,
         template<class> class SharedArray1D=af::shared>
class tertiary_CH
  : public geometrical_hydrogens<tertiary_CH<FloatType,
                                                   XrayScattererType,
                                                   SharedArray1D>,
                                 FloatType, XrayScattererType,
                                 af::tiny, 1,
                                 SharedArray1D>
{
  public:
    typedef geometrical_hydrogens<tertiary_CH<FloatType,
                                                   XrayScattererType,
                                                   SharedArray1D>,
                                  FloatType, XrayScattererType,
                                  af::tiny, 1,
                                  SharedArray1D>
            base_t;
    using base_t::i_pivot;
    using base_t::i_hydrogens;
    using base_t::l;
    using base_t::dx_over_dl;

    typedef XrayScattererType xray_scatterer_type;
    typedef FloatType float_type;
    typedef parameter_map<xray_scatterer_type> parameter_map_type;
    typedef cartesian<float_type> cart_t;
    typedef fractional<float_type> frac_t;

    tertiary_CH(int pivot,
                af::tiny<int, 3> pivot_neighbours,
                int hydrogen,
                float_type bond_length,
                bool stretching=false)
      : base_t(pivot, hydrogen, bond_length, stretching),
        i_pivot_neighbours(pivot_neighbours)
    {}

    void place_constrained_scatterers(
      uctbx::unit_cell const &unit_cell,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::ref<xray_scatterer_type> const &scatterers)
    {

      cart_t x_p = unit_cell.orthogonalize(scatterers[i_pivot].site);
      cart_t
        x_X = unit_cell.orthogonalize(scatterers[i_pivot_neighbours[0]].site),
        x_Y = unit_cell.orthogonalize(scatterers[i_pivot_neighbours[1]].site),
        x_Z = unit_cell.orthogonalize(scatterers[i_pivot_neighbours[2]].site);
      cart_t u_XC = (x_p - x_X).normalize(),
             u_YC = (x_p - x_Y).normalize(),
             u_ZC = (x_p - x_Z).normalize();
      cart_t u = u_XC - u_YC;
      cart_t v = u_YC - u_ZC;
      cart_t e0 = u.cross(v).normalize();
      if (e0*(u_XC + u_YC + u_ZC) < 0) e0 = -e0;
      cart_t x_h = x_p + l*e0;
      scatterers[i_hydrogens[0]].site = unit_cell.fractionalize(x_h);
      dx_over_dl[0] = e0;
    }

  private:
    af::tiny<int, 3> i_pivot_neighbours;

};


/// Model of aromatic C-H or amide N-H
/** The other 2 neighbours of C or N being X and Y, X-C-Y (resp. X-N-Y)
    is bisected by C-H (resp. N-H).
*/

template<typename FloatType, class XrayScattererType,
         template<class> class SharedArray1D=af::shared>
class aromatic_CH_or_amide_NH
  : public geometrical_hydrogens<aromatic_CH_or_amide_NH<FloatType,
                                                         XrayScattererType,
                                                         SharedArray1D>,
                                 FloatType, XrayScattererType,
                                 af::tiny, 1,
                                 SharedArray1D>
{
  public:
    typedef geometrical_hydrogens<aromatic_CH_or_amide_NH<FloatType,
                                                         XrayScattererType,
                                                         SharedArray1D>,
                                  FloatType, XrayScattererType,
                                  af::tiny, 1,
                                  SharedArray1D>
            base_t;
    using base_t::i_pivot;
    using base_t::i_hydrogens;
    using base_t::l;
    using base_t::dx_over_dl;

    typedef XrayScattererType xray_scatterer_type;
    typedef FloatType float_type;
    typedef parameter_map<xray_scatterer_type> parameter_map_type;
    typedef cartesian<float_type> cart_t;
    typedef fractional<float_type> frac_t;

    aromatic_CH_or_amide_NH(int pivot,
                            af::tiny<int, 2> pivot_neighbours,
                            int hydrogen,
                            float_type bond_length,
                            bool stretching=false)
      : base_t(pivot, hydrogen, bond_length, stretching),
        i_pivot_neighbours(pivot_neighbours)
    {}

    void place_constrained_scatterers(
      uctbx::unit_cell const &unit_cell,
      sgtbx::site_symmetry_table const &site_symmetry_table,
      af::ref<xray_scatterer_type> const &scatterers)
    {
      cart_t x_p = unit_cell.orthogonalize(scatterers[i_pivot].site);
      cart_t
        x_X = unit_cell.orthogonalize(scatterers[i_pivot_neighbours[0]].site),
        x_Y = unit_cell.orthogonalize(scatterers[i_pivot_neighbours[1]].site);
      cart_t u_XC = (x_p - x_X).normalize(),
             u_YC = (x_p - x_Y).normalize();
      cart_t e0 = (u_XC + u_YC).normalize();
      cart_t x_h = x_p + l*e0;
      scatterers[i_hydrogens[0]].site = unit_cell.fractionalize(x_h);
      dx_over_dl[0] = e0;
    }

  private:
    af::tiny<int, 2> i_pivot_neighbours;
};


}}} // namespace smtbx::refinement::constraints

#endif // GUARD
