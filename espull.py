import sys
import os
import optparse
import pyes
import json

from analyser import *
from formatter import *

analysers = {
    'build' : BuildAnalyser,
    'comp' : ComponentAnalyser,
    'run' : RunAnalyser,
}

formatters = {
    'json' : JsonFormatter,
    'csv' : CSVFormatter,
}

basic_fields = ['revision', 'machine', 'starttime']
parametric_fields = ['testgroup', 'testsuite', 'os', 'buildtype', 'tree']

def parse_results(data, analyser, spec_fields):
  """ Parses a testrun document """
  template = {}
  for field in basic_fields:
    template[field] = data.get(field, None)
  for field in spec_fields:
    template[field] = data.get(field, None)

  test_data = data['testruns']
  results = None
  if 'format' not in data:
    print "no format, skipping"
  else:
    data_obj = TestSuite(test_data, data['format'] == 'ts_format')
    results = analyser.parse_data(data_obj, template)

  return results

def request_data(args):
  address = args.get("es_server", "localhost:9200")
  print "Connecting to: %s" % address
  conn = pyes.ES(address)

  query = pyes.query.ConstantScoreQuery()

  spec_fields = []
  strip_fields = args.get("strip_fields", False)

  for field in parametric_fields:
    if field in args:
      val = args.get(field)

      # allow OR specs
      or_filters = []
      for or_seg in val.split('|'):
        and_filters = []
        # hack to allow filtering on trees as ES tokenizes on -
        for and_seg in or_seg.split('-'):
          and_filters.append(pyes.filters.TermFilter(field, and_seg))
        or_filters.append(pyes.filters.ANDFilter(and_filters))
      query.add(pyes.filters.ORFilter(or_filters))

      if not strip_fields or len(or_filters) > 1:
        spec_fields.append(field)
    else:
      spec_fields.append(field)

  if "from" in args and "to" in args:
    erange = pyes.utils.ESRange("date", from_value=args.get("from"), to_value=args.get("to"))
    query.add(pyes.filters.RangeFilter(erange))

  print "Query: %s" % query.serialize()

  size = args.get("size", 20)
  if args.get("all", False):
    print "Retrieving count"
    data = conn.count(query)
    size = data.get("count")

  print "Retrieving Data"
  data = conn.search(query=query, size=size, indexes=[args.get('index','talos')])

  print "Data: %d/%d" % (len(data["hits"]["hits"]), data["hits"]["total"])

  analyser_name = args.get("analyser", "graph")
  analyser = analysers.get(analyser_name, None)
  if analyser is None:
    print "Unrecognized analyser: %s" % analyser_name
    return

  analyser = analyser()

  if args.get("dump",False):
    print data
    return

  results = []
  for dp in data['hits']['hits']:
    if dp['_type'] == 'testruns':
      result = parse_results(dp['_source'], analyser, spec_fields)
      if result:
        results.extend(result)

  out_format = args.get("format", "json")
  formatter = formatters.get(out_format, None)
  if formatter is None:
    print "Unrecognized formatter: %s" % out_format
    return

  headers = []
  headers.extend(basic_fields)
  headers.extend(spec_fields)
  headers.extend(analyser.get_headers())

  if 'output' in args:
    output = open(args.get('output'), 'w')
  else:
    output = os.fdopen(sys.stdout.fileno(), 'w')

  formatter(headers=headers).output_records(results, output)

  output.close()

def cli():
  usage = "usage: %prog [options]"
  parser = optparse.OptionParser(usage=usage)

  # server spec options
  parser.add_option("--es-server", dest="es_server", help="ES Server to query", action="store", default="localhost:9200")
  parser.add_option("--index", dest="index", help="Index to query", action="store", default="talos")

  # query spec options
  parser.add_option("--from", dest="from_date", help="Start Date of query YYYY-MM-DD (also needs --to)", action="store")
  parser.add_option("--to", dest="to", help="End Date of query YYYY-MM-DD (also needs --from)", action="store")
  parser.add_option("--tree", dest="tree", help="Tree to query", action="store")
  parser.add_option("--testsuite", dest="testsuite", help="Test to query", action="store")
  parser.add_option("--testgroup", dest="testgroup", help="Testgroup to query", action="store")
  parser.add_option("--os", dest="os", help="OS to query", action="store")
  parser.add_option("--buildtype", dest="buildtype", help="Buildtype to query", action="store")

  # result size options
  parser.add_option("--all", dest="all", help="Retrieve all results", action="store_true")
  parser.add_option("--size", dest="size", help="Size of query, overridden by --all", action="store", default=20)

  # output options
  parser.add_option("--format", dest="format", help="Output format (json, csv)", action="store", default="csv")
  parser.add_option("--output", dest="output", help="File to dump output to", action="store")
  parser.add_option("--dump", dest="dump", help="Dump raw ES results to stdout", action="store_true")
  parser.add_option("--analyser", dest="analyser", help="Analyser to use for summarization, options=(build, comp, run)",
                    action="store", default="build")
  parser.add_option("--strip-spec-fields", dest="strip_fields", help="Remove fields constrained by a spec option from output",
                    action="store_true")

  (options, args) = parser.parse_args()

  request = {"es_server":options.es_server,
             "dump":options.dump,
             "all":options.all,
             "size":options.size,
             "format":options.format,
             "analyser":options.analyser,
             "strip_fields":options.strip_fields,
             "index":options.index,
             }

  if options.from_date:
    request.update({"from":options.from_date})
  if options.to:
    request.update({"to":options.to})
  if options.tree:
    request.update({"tree":options.tree})
  if options.testsuite:
    request.update({"testsuite":options.testsuite})
  if options.testgroup:
    request.update({"testgroup":options.testgroup})
  if options.os:
    request.update({"os":options.os})
  if options.buildtype:
    request.update({"buildtype":options.buildtype})
  if options.output:
    request.update({"output":options.output})

  request_data(request)

if __name__ == "__main__":
  cli()
