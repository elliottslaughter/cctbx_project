#ifndef CCTBX_RESTRAINTS_BOND_H
#define CCTBX_RESTRAINTS_BOND_H

#include <cctbx/restraints/utils.h>
#include <cctbx/crystal/direct_space_asu.h>
#include <set>

namespace cctbx { namespace restraints {

  namespace direct_space_asu = cctbx::crystal::direct_space_asu;

  struct bond_proxy
  {
    bond_proxy() {}

    bond_proxy(
      af::tiny<std::size_t, 2> const& i_seqs_,
      double distance_ideal_,
      double weight_)
    :
      i_seqs(i_seqs_),
      distance_ideal(distance_ideal_),
      weight(weight_)
    {}

    af::tiny<std::size_t, 2> i_seqs;
    double distance_ideal;
    double weight;
  };

  struct bond_sym_proxy
  {
    bond_sym_proxy() {}

    bond_sym_proxy(
      direct_space_asu::asu_mapping_index_pair const& pair_,
      double distance_ideal_,
      double weight_)
    :
      pair(pair_),
      distance_ideal(distance_ideal_),
      weight(weight_)
    {}

    bond_proxy
    as_bond_proxy() const
    {
      return bond_proxy(
        af::tiny<std::size_t, 2>(pair.i_seq, pair.j_seq),
        distance_ideal,
        weight);
    }

    direct_space_asu::asu_mapping_index_pair pair;
    double distance_ideal;
    double weight;
  };

  class bond
  {
    public:
      typedef scitbx::vec3<double> vec3;

      bond() {}

      bond(
        af::tiny<scitbx::vec3<double>, 2> const& sites_,
        double distance_ideal_,
        double weight_)
      :
        sites(sites_),
        distance_ideal(distance_ideal_),
        weight(weight_)
      {
        init_distance_model();
      }

      bond(
        af::const_ref<scitbx::vec3<double> > const& sites_cart,
        bond_proxy const& proxy)
      :
        distance_ideal(proxy.distance_ideal),
        weight(proxy.weight)
      {
        for(int i=0;i<2;i++) {
          std::size_t i_seq = proxy.i_seqs[i];
          CCTBX_ASSERT(i_seq < sites_cart.size());
          sites[i] = sites_cart[i_seq];
        }
        init_distance_model();
      }

      bond(
        af::const_ref<scitbx::vec3<double> > const& sites_cart,
        direct_space_asu::asu_mappings<> const& asu_mappings,
        bond_sym_proxy const& proxy)
      :
        distance_ideal(proxy.distance_ideal),
        weight(proxy.weight)
      {
        sites[0] = asu_mappings.map_moved_site_to_asu(
          sites_cart[proxy.pair.i_seq], proxy.pair.i_seq, 0);
        sites[1] = asu_mappings.map_moved_site_to_asu(
          sites_cart[proxy.pair.j_seq], proxy.pair.j_seq, proxy.pair.j_sym);
        init_distance_model();
      }

      double
      residual() const { return weight * scitbx::fn::pow2(delta); }

      // Not available in Python.
      scitbx::vec3<double>
      gradient_0() const
      {
        return -weight * 2 * delta / distance_model * (sites[0] - sites[1]);
      }

      af::tiny<scitbx::vec3<double>, 2>
      gradients() const
      {
        af::tiny<vec3, 2> result;
        result[0] = gradient_0();
        result[1] = -result[0];
        return result;
      }

      // Not available in Python.
      void
      add_gradients(
        af::ref<scitbx::vec3<double> > const& gradient_array,
        af::tiny<std::size_t, 2> const& i_seqs) const
      {
        vec3 g0 = gradient_0();
        gradient_array[i_seqs[0]] += g0;
        gradient_array[i_seqs[1]] += -g0;
      }

      // Not available in Python.
      void
      add_gradients(
        af::ref<scitbx::vec3<double> > const& gradient_array,
        direct_space_asu::asu_mappings<> const& asu_mappings,
        direct_space_asu::asu_mapping_index_pair const& pair) const
      {
        vec3 grad_asu = gradient_0();
        vec3 grad_i_seq = asu_mappings.r_inv_cart(pair.i_seq, 0) * grad_asu;
        gradient_array[pair.i_seq] += grad_i_seq;
        if (pair.j_sym == 0) {
          vec3 grad_j_seq = asu_mappings.r_inv_cart(pair.j_seq, 0) * grad_asu;
          gradient_array[pair.j_seq] -= grad_j_seq;
        }
      }

      af::tiny<scitbx::vec3<double>, 2> sites;
      double distance_ideal;
      double weight;
      double distance_model;
      double delta;

    protected:
      void
      init_distance_model()
      {
        distance_model = (sites[0] - sites[1]).length();
        delta = distance_ideal - distance_model;
      }
  };

  class bond_sorted_proxies
  {
    public:
      bond_sorted_proxies() {}

      bond_sorted_proxies(
        boost::shared_ptr<
          direct_space_asu::asu_mappings<> > const& asu_mappings)
      :
        asu_mappings_owner_(asu_mappings),
        asu_mappings_(asu_mappings.get())
      {}

      //! Instance as passed to the constructor.
      boost::shared_ptr<direct_space_asu::asu_mappings<> > const&
      asu_mappings() const { return asu_mappings_owner_; }

      bool
      process(bond_proxy const& proxy)
      {
        proxies.push_back(proxy);
        return false;
      }

      bool
      process(bond_sym_proxy const& proxy)
      {
        if (asu_mappings_->is_direct_interaction(proxy.pair)) {
          if (proxy.pair.j_sym == 0 || proxy.pair.i_seq < proxy.pair.j_seq) {
            proxies.push_back(proxy.as_bond_proxy());
          }
          return false;
        }
        sym_proxies.push_back(proxy);
        return true;
      }

      std::size_t
      n_total() const
      {
        return proxies.size() + sym_proxies.size();
      }

    protected:
      boost::shared_ptr<direct_space_asu::asu_mappings<> > asu_mappings_owner_;
      const direct_space_asu::asu_mappings<>* asu_mappings_;

    public:
      af::shared<bond_proxy> proxies;
      af::shared<bond_sym_proxy> sym_proxies;
  };

  inline
  af::shared<double>
  bond_deltas(
    af::const_ref<scitbx::vec3<double> > const& sites_cart,
    af::const_ref<bond_proxy> const& proxies)
  {
    return detail::generic_deltas<bond_proxy, bond>::get(
      sites_cart, proxies);
  }

  inline
  af::shared<double>
  bond_residuals(
    af::const_ref<scitbx::vec3<double> > const& sites_cart,
    af::const_ref<bond_proxy> const& proxies)
  {
    return detail::generic_residuals<bond_proxy, bond>::get(
      sites_cart, proxies);
  }

  inline
  double
  bond_residual_sum(
    af::const_ref<scitbx::vec3<double> > const& sites_cart,
    af::const_ref<bond_proxy> const& proxies,
    af::ref<scitbx::vec3<double> > const& gradient_array)
  {
    return detail::generic_residual_sum<bond_proxy, bond>::get(
      sites_cart, proxies, gradient_array);
  }

  inline
  af::shared<double>
  bond_deltas(
    af::const_ref<scitbx::vec3<double> > const& sites_cart,
    direct_space_asu::asu_mappings<> const& asu_mappings,
    af::const_ref<bond_sym_proxy> const& proxies)
  {
    af::shared<double> result((af::reserve(sites_cart.size())));
    for(std::size_t i=0;i<proxies.size();i++) {
      bond restraint(sites_cart, asu_mappings,  proxies[i]);
      result.push_back(restraint.delta);
    }
    return result;
  }

  inline
  af::shared<double>
  bond_residuals(
    af::const_ref<scitbx::vec3<double> > const& sites_cart,
    direct_space_asu::asu_mappings<> const& asu_mappings,
    af::const_ref<bond_sym_proxy> const& proxies)
  {
    af::shared<double> result((af::reserve(sites_cart.size())));
    for(std::size_t i=0;i<proxies.size();i++) {
      bond restraint(sites_cart, asu_mappings,  proxies[i]);
      result.push_back(restraint.residual());
    }
    return result;
  }

  inline
  double
  bond_residual_sum(
    af::const_ref<scitbx::vec3<double> > const& sites_cart,
    direct_space_asu::asu_mappings<> const& asu_mappings,
    af::const_ref<bond_sym_proxy> const& proxies,
    af::ref<scitbx::vec3<double> > const& gradient_array)
  {
    double result = 0;
    for(std::size_t i=0;i<proxies.size();i++) {
      bond restraint(sites_cart, asu_mappings, proxies[i]);
      if (proxies[i].pair.j_sym == 0) result += restraint.residual();
      else                            result += restraint.residual()*.5;
      if (gradient_array.size() != 0) {
        restraint.add_gradients(gradient_array, asu_mappings, proxies[i].pair);
      }
    }
    return result;
  }

  inline
  double
  bond_residual_sum(
    af::const_ref<scitbx::vec3<double> > const& sites_cart,
    bond_sorted_proxies const& sorted_proxies,
    af::ref<scitbx::vec3<double> > const& gradient_array)
  {
    double result = bond_residual_sum(
      sites_cart,
      sorted_proxies.proxies.const_ref(),
      gradient_array);
    result += bond_residual_sum(
      sites_cart,
      *sorted_proxies.asu_mappings(),
      sorted_proxies.sym_proxies.const_ref(),
      gradient_array);
    return result;
  }

  inline
  af::shared<std::set<std::size_t> >
  bond_sets(
    std::size_t n_sites,
    af::const_ref<restraints::bond_proxy> const& bond_proxies)
  {
    af::shared<std::set<std::size_t> > result;
    result.resize(n_sites);
    for(std::size_t i=0;i<bond_proxies.size();i++) {
      restraints::bond_proxy const& proxy = bond_proxies[i];
      CCTBX_ASSERT(proxy.i_seqs[0] < n_sites);
      CCTBX_ASSERT(proxy.i_seqs[1] < n_sites);
      result[proxy.i_seqs[0]].insert(proxy.i_seqs[1]);
      result[proxy.i_seqs[1]].insert(proxy.i_seqs[0]);
    }
    return result;
  }

}} // namespace cctbx::restraints

#endif // CCTBX_RESTRAINTS_BOND_H
