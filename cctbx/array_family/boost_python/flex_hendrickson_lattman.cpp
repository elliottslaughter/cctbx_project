#include <cctbx/boost_python/flex_fwd.h>

#include <scitbx/array_family/boost_python/flex_wrapper.h>
#include <scitbx/boost_python/pickle_single_buffered.h>
#include <boost/python/args.hpp>
#include <boost/python/make_constructor.hpp>

namespace scitbx { namespace boost_python { namespace pickle_single_buffered {

  inline
  char* to_string(char* start, cctbx::hendrickson_lattman<> const& value)
  {
    return to_string(to_string(to_string(to_string(start,
      value[0]), value[1]), value[2]), value[3]);
  }

  template <>
  struct from_string<cctbx::hendrickson_lattman<> >
  {
    from_string(const char* start)
    {
      end = start;
      for(std::size_t i=0;i<4;i++) {
        from_string<double> proxy(end);
        value[i] = proxy.value;
        end = proxy.end;
      }
    }

    cctbx::hendrickson_lattman<> value;
    const char* end;
  };

}}} // namespace scitbx::boost_python::pickle_single_buffered

#include <scitbx/array_family/boost_python/flex_pickle_single_buffered.h>

namespace scitbx { namespace af { namespace boost_python {

namespace {

  flex<cctbx::hendrickson_lattman<> >::type*
  from_phase_integrals(
    af::const_ref<bool> const& centric_flags,
    af::const_ref<std::complex<double> > const& phase_integrals,
    double max_figure_of_merit)
  {
    CCTBX_ASSERT(phase_integrals.size() == centric_flags.size());
    af::shared<cctbx::hendrickson_lattman<> > result;
    result.reserve(centric_flags.size());
    for(std::size_t i=0;i<centric_flags.size();i++) {
      result.push_back(cctbx::hendrickson_lattman<>(
        centric_flags[i],
        phase_integrals[i],
        max_figure_of_merit));
    }
    return new flex<cctbx::hendrickson_lattman<> >::type(
      result, result.size());
  }

} // namespace <anonymous>

  void wrap_flex_hendrickson_lattman()
  {
    using namespace boost::python;
    typedef flex_wrapper<cctbx::hendrickson_lattman<> > f_w;
    f_w::plain("hendrickson_lattman")
      .def_pickle(flex_pickle_single_buffered<cctbx::hendrickson_lattman<>,
        4*pickle_size_per_element<
          cctbx::hendrickson_lattman<>::base_type::value_type>::value>())
      .def("__init__", make_constructor(
        from_phase_integrals,
        default_call_policies(),
        (arg_("centric_flags"),
         arg_("phase_integrals"),
         arg_("max_figure_of_merit"))))
      .def("__add__", f_w::add_a_a)
      .def("__iadd__", f_w::iadd_a_a)
    ;
  }

}}} // namespace scitbx::af::boost_python
