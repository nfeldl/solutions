"""Flask App for http://codeearth.net."""

import io
import json
import os

import advanced_controls
from flask import Flask, request, render_template, jsonify, Response
import pandas as pd
from model import firstcost
from model import unitadoption
import werkzeug.exceptions


app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False  # minify JSON


@app.route("/", methods=['GET'])
def home():
    '''Simple home page with links to documentation, license and source code'''
    # Allow overriding of repo URL in environment for people hosting a fork etc.
    repo = os.getenv('DRAWDOWN_REPO', "https://gitlab.com/codeearth/drawdown")
    return render_template('home.html', repo=repo)


@app.route("/unitadoption", methods=['POST'])
def unitAdoption():
    '''Initial version of the API - only implements the na_funits calculation.'''
    ref_sol_funits = to_csv(request.json, 'ref', app.logger)
    pds_sol_funits = to_csv(request.json, 'pds', app.logger)

    ua = unitadoption.UnitAdoption()
    return ua.na_funits(ref_sol_funits, pds_sol_funits).to_csv(index=False)


@app.route("/unitadoption.v2", methods=['POST'])
def unitAdoption2():
    '''Second version of the API - implements most of the unit adoption tab.'''
    js = request.get_json(force=True)
    ref_sol_funits = to_csv(js, 'ref_sol_funits', app.logger)
    pds_sol_funits = to_csv(js, 'pds_sol_funits', app.logger)
    aau_sol_funits = js['aau_sol_funits']
    life_cap_sol_funits = js['life_cap_sol_funits']
    aau_conv_funits = js['aau_conv_funits']
    life_cap_conv_funits = js['life_cap_conv_funits']
    ref_tam_funits = to_csv(js, 'ref_tam_funits', app.logger)
    pds_tam_funits = to_csv(js, 'pds_tam_funits', app.logger)

    ua = unitadoption.UnitAdoption()
    results = dict()
    results['na_funits'] = ua.na_funits(
        ref_sol_funits, pds_sol_funits).to_csv()
    results['pds_sol_cum_iunits'] = ua.sol_cum_iunits(
        pds_sol_funits, aau_sol_funits).to_csv()
    results['ref_sol_cum_iunits'] = ua.sol_cum_iunits(
        ref_sol_funits, aau_sol_funits).to_csv()
    results['life_rep_sol_years'] = ua.life_rep_years(
        life_cap_sol_funits, aau_sol_funits)
    results['life_rep_conv_years'] = ua.life_rep_years(
        life_cap_conv_funits, aau_conv_funits)
    return jsonify(results)


@app.route("/firstcost", methods=['POST'])
def firstCost():
    '''Implements First Cost tab from Excel model implementation.'''
    js = request.get_json(force=True)
    ac_rq = to_advanced_controls(js, app.logger)
    fc_rq = js.get('first_cost', {})
    ua_rq = js.get('unit_adoption', {})
    fc = firstcost.FirstCost(
        ac=ac_rq,
        pds_learning_increase_mult=fc_rq.get('pds_learning_increase_mult', 0),
        ref_learning_increase_mult=fc_rq.get('ref_learning_increase_mult', 0),
        conv_learning_increase_mult=fc_rq.get('conv_learning_increase_mult', 0))

    funits = ua_rq.get('soln_pds_tot_iunits_reqd', [])
    soln_pds_tot_iunits_reqd = pd.DataFrame(funits[1:], columns=funits[0]).set_index('Year')
    funits = ua_rq.get('conv_ref_tot_iunits_reqd', [])
    conv_ref_tot_iunits_reqd = pd.DataFrame(funits[1:], columns=funits[0]).set_index('Year')
    funits = ua_rq.get('soln_ref_tot_iunits_reqd', [])
    soln_ref_tot_iunits_reqd = pd.DataFrame(funits[1:], columns=funits[0]).set_index('Year')
    iunits = ua_rq.get('soln_pds_new_iunits_reqd', [])
    soln_pds_new_iunits_reqd = pd.DataFrame(iunits[1:], columns=iunits[0]).set_index('Year')
    iunits = ua_rq.get('soln_ref_new_iunits_reqd', [])
    soln_ref_new_iunits_reqd = pd.DataFrame(iunits[1:], columns=iunits[0]).set_index('Year')
    iunits = ua_rq.get('conv_ref_new_iunits_reqd', [])
    iunits = [x for x in iunits if x[0] != 'Lifetime']
    conv_ref_new_iunits_reqd = pd.DataFrame(iunits[1:], columns=iunits[0]).set_index('Year')

    results = dict()
    soln_pds_install_cost_per_iunit = fc.soln_pds_install_cost_per_iunit(
        soln_pds_tot_iunits_reqd=soln_pds_tot_iunits_reqd,
        conv_ref_tot_iunits_reqd=conv_ref_tot_iunits_reqd)
    results['soln_pds_install_cost_per_iunit'] = format_for_response(soln_pds_install_cost_per_iunit)
    conv_ref_install_cost_per_iunit = fc.conv_ref_install_cost_per_iunit(
        conv_ref_tot_iunits_reqd=conv_ref_tot_iunits_reqd)
    results['conv_ref_install_cost_per_iunit'] = format_for_response(
        conv_ref_install_cost_per_iunit)
    soln_ref_install_cost_per_iunit = fc.soln_ref_install_cost_per_iunit(
        soln_ref_tot_iunits_reqd, conv_ref_tot_iunits_reqd)
    results['soln_ref_install_cost_per_iunit'] = format_for_response(
        soln_ref_install_cost_per_iunit)
    soln_pds_annual_world_first_cost = fc.soln_pds_annual_world_first_cost(
        soln_pds_new_iunits_reqd=soln_pds_new_iunits_reqd,
        soln_pds_install_cost_per_iunit=soln_pds_install_cost_per_iunit)
    results['soln_pds_annual_world_first_cost'] = format_for_response(
        soln_pds_annual_world_first_cost)
    results['soln_pds_cumulative_install'] = format_for_response(
        fc.soln_pds_cumulative_install(soln_pds_annual_world_first_cost))
    soln_ref_annual_world_first_cost = fc.soln_ref_annual_world_first_cost(
        soln_ref_new_iunits_reqd, soln_ref_install_cost_per_iunit)
    results['soln_ref_annual_world_first_cost'] = format_for_response(
        soln_ref_annual_world_first_cost)
    conv_ref_annual_world_first_cost = fc.conv_ref_annual_world_first_cost(
        conv_ref_new_iunits_reqd, conv_ref_install_cost_per_iunit)
    results['conv_ref_annual_world_first_cost'] = format_for_response(
        conv_ref_annual_world_first_cost)
    results['ref_cumulative_install'] = format_for_response(fc.ref_cumulative_install(
        conv_ref_annual_world_first_cost, soln_ref_annual_world_first_cost))
    results_str = json.dumps(results)
    return Response(response=results_str, status=200, mimetype="application/json")


@app.route("/unitadoption.v3", methods=['POST'])
def unitAdoption3():
    """Third version of the API, switches to JSON with no CSV."""
    js = request.get_json(force=True)
    ac_rq = to_advanced_controls(js, app.logger)
    ua_rq = js.get('unit_adoption', {})
    tpr = ua_rq.get('ref_tam_per_region', [])
    ref_tam_per_region = pd.DataFrame(tpr[1:], columns=tpr[0]).set_index('Year')
    tpr = ua_rq.get('pds_tam_per_region', [])
    pds_tam_per_region = pd.DataFrame(tpr[1:], columns=tpr[0]).set_index('Year')
    funits = ua_rq.get('soln_pds_funits_adopted', [])
    soln_pds_funits_adopted = pd.DataFrame(funits[1:], columns=funits[0]).set_index('Year')
    funits = ua_rq.get('soln_ref_funits_adopted', [])
    soln_ref_funits_adopted = pd.DataFrame(funits[1:], columns=funits[0]).set_index('Year')

    ua = unitadoption.UnitAdoption(ac=ac_rq)
    results = dict()
    ref_population = ua.ref_population()
    results['ref_population'] = format_for_response(ref_population)
    ref_gdp = ua.ref_gdp()
    results['ref_gdp'] = format_for_response(ref_gdp)
    ref_gdp_per_capita = ua.ref_gdp_per_capita(ref_population, ref_gdp)
    results['ref_gdp_per_capita'] = format_for_response(ref_gdp_per_capita)
    results['ref_tam_per_capita'] = format_for_response(
        ua.ref_tam_per_capita(ref_tam_per_region, ref_population))
    results['ref_tam_per_gdp_per_capita'] = format_for_response(
        ua.ref_tam_per_gdp_per_capita(ref_tam_per_region, ref_gdp_per_capita))
    results['ref_tam_growth'] = format_for_response(ua.ref_tam_growth(ref_tam_per_region))
    pds_population = ua.pds_population()
    results['pds_population'] = format_for_response(pds_population)
    pds_gdp = ua.pds_gdp()
    results['pds_gdp'] = format_for_response(pds_gdp)
    pds_gdp_per_capita = ua.pds_gdp_per_capita(pds_population, pds_gdp)
    results['pds_gdp_per_capita'] = format_for_response(pds_gdp_per_capita)
    results['pds_tam_per_capita'] = format_for_response(
        ua.pds_tam_per_capita(pds_tam_per_region, pds_population))
    results['pds_tam_per_gdp_per_capita'] = format_for_response(
        ua.pds_tam_per_gdp_per_capita(pds_tam_per_region, pds_gdp_per_capita))
    results['pds_tam_growth'] = format_for_response(ua.pds_tam_growth(pds_tam_per_region))
    s = ua.soln_pds_cumulative_funits(soln_pds_funits_adopted)
    results['soln_pds_cumulative_funits'] = format_for_response(
        ua.soln_pds_cumulative_funits(soln_pds_funits_adopted))
    results['soln_ref_cumulative_funits'] = format_for_response(
        ua.soln_ref_cumulative_funits(soln_ref_funits_adopted))
    soln_net_annual_funits_adopted = ua.soln_net_annual_funits_adopted(
        soln_ref_funits_adopted, soln_pds_funits_adopted)
    results['soln_net_annual_funits_adopted'] = format_for_response(soln_net_annual_funits_adopted)
    soln_pds_tot_iunits_reqd = ua.soln_pds_tot_iunits_reqd(soln_pds_funits_adopted)
    results['soln_pds_tot_iunits_reqd'] = format_for_response(soln_pds_tot_iunits_reqd)
    results['soln_pds_new_iunits_reqd'] = format_for_response(
      ua.soln_pds_new_iunits_reqd(soln_pds_tot_iunits_reqd))
    results['soln_pds_big4_iunits_reqd'] = format_for_response(
        ua.soln_pds_big4_iunits_reqd(soln_pds_tot_iunits_reqd))
    soln_ref_tot_iunits_reqd = ua.soln_ref_tot_iunits_reqd(soln_ref_funits_adopted)
    results['soln_ref_tot_iunits_reqd'] = format_for_response(soln_ref_tot_iunits_reqd)
    results['soln_ref_new_iunits_reqd'] = format_for_response(
      ua.soln_ref_new_iunits_reqd(soln_ref_tot_iunits_reqd))
    results['conv_ref_tot_iunits_reqd'] = format_for_response(
        ua.conv_ref_tot_iunits_reqd(ref_tam_per_region, soln_ref_funits_adopted))
    conv_ref_annual_tot_iunits = ua.conv_ref_annual_tot_iunits(soln_net_annual_funits_adopted)
    results['conv_ref_annual_tot_iunits'] = format_for_response(conv_ref_annual_tot_iunits)
    results['conv_ref_new_iunits_reqd'] = format_for_response(
        ua.conv_ref_new_iunits_reqd(conv_ref_annual_tot_iunits))
    results['conv_lifetime_replacement'] = format_for_response(ua.conv_lifetime_replacement())

    results['soln_pds_net_grid_electricity_units_saved'] = format_for_response(
        ua.soln_pds_net_grid_electricity_units_saved(soln_net_annual_funits_adopted))
    results['soln_pds_net_grid_electricity_units_used'] = format_for_response(
        ua.soln_pds_net_grid_electricity_units_used(soln_net_annual_funits_adopted))
    results['soln_pds_fuel_units_avoided'] = format_for_response(
        ua.soln_pds_fuel_units_avoided(soln_net_annual_funits_adopted))
    results['soln_pds_direct_co2_emissions_saved'] = format_for_response(
        ua.soln_pds_direct_co2_emissions_saved(soln_net_annual_funits_adopted))

    if ac_rq.ch4_is_co2eq:
      ch4 = ua.soln_pds_direct_ch4_co2_emissions_saved(soln_net_annual_funits_adopted,
          ch4_co2equiv_per_funit=ac_rq.ch4_co2_per_twh)
    else:
      ch4 = ua.soln_pds_direct_ch4_co2_emissions_saved(soln_net_annual_funits_adopted,
          ch4_per_funit=ac_rq.ch4_co2_per_twh)
    results['soln_pds_direct_ch4_co2_emissions_saved'] = format_for_response(ch4)

    if ac_rq.n2o_is_co2eq:
      n2o = ua.soln_pds_direct_n2o_co2_emissions_saved(soln_net_annual_funits_adopted,
          n2o_co2equiv_per_funit=ac_rq.n2o_co2_per_twh)
    else:
      n2o = ua.soln_pds_direct_n2o_co2_emissions_saved(soln_net_annual_funits_adopted,
          n2o_per_funit=ac_rq.n2o_co2_per_twh)
    results['soln_pds_direct_n2o_co2_emissions_saved'] = format_for_response(n2o)

    results_str = json.dumps(results)
    return Response(response=results_str, status=200, mimetype="application/json")


def to_csv(data, key, logger):
    '''
    Helper function to load CSV from input data dictionary.
    '''
    csvstr = data[key]
    csvio = io.StringIO(csvstr)
    csv = pd.read_csv(csvio)
    logger.info("%s parsed as:\n%s", key, csv)
    return csv


def to_advanced_controls(data, logger):
    '''Helper function to extract advanced controls fields.'''
    if not data.get('advanced_controls'):
        raise werkzeug.exceptions.BadRequest('advanced_controls missing')
    ac = data['advanced_controls']
    return advanced_controls.AdvancedControls(**ac)


def format_for_response(df):
  if isinstance(df, pd.DataFrame):
    return [[df.index.name, *df.columns.tolist()]] + df.reset_index().dropna().values.tolist()
  elif isinstance(df, pd.Series):
    return [[df.index.name, df.name]] + df.reset_index().dropna().values.tolist()
  else:
    return str(df)


def shutdown():
    '''
    Shut down the server and exit.

    By default, no route to this function is installed. The production server does not
    have a URL exposed which will cause it to exit. Unit tests will add a route to
    the instance they are running within the test, allowing the server to be stopped.
    '''
    func = request.environ.get('werkzeug.server.shutdown')
    func()
    return 'Server shutting down...'


def get_app_for_tests():
    '''
    Return the app object for tests to use.
    '''
    return app
