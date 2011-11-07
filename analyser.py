
__all__ = ['TestSuite', 'BuildAnalyser', 'ComponentAnalyser']

def get_median(data, strip_max=False, strip_first=False):
  d = data
  if strip_first:
    d = data[1:]
  d = sorted(d)
  if strip_max:
    d = d[:-1]
  if len(d) % 2 == 1:
    return d[len(d)/2]
  return (d[len(d)/2 - 1] + d[len(d)/2])/2

def get_average(data, strip_max=False):
  total = sum(data)
  size = len(data)
  if strip_max:
    total -= max(data)
    size -= 1
  return total / size

class TestComponent(object):
  def __init__(self, values):
    self.values = values
    self.min = min(values)
    self.max = max(values)

  # For TP tests
  def get_median(self, **kwargs):
    return get_median(self.values, **kwargs)

  # For TS Tets
  def get_average(self, **kwargs):
    return get_average(self.values, **kwargs)

  def __len__(self):
    return len(self.values)

class TestSuite(object):
  def __init__(self, data, is_ts=False):
    self._data = data
    self.is_ts = is_ts
    self.components = {}
    for key, value in self._data.items():
      self.components[key] = TestComponent([float(v) for v in value.split(',')])

  def __len__(self):
    return len(self.components)

  @property
  def old_average(self):
    if self.is_ts:
      assert(len(self) == 1)
      comp = self.components.values()[0]
      return comp.get_average(strip_max=True)
    else:
      return get_average([comp.get_median(strip_max=True) for comp in self.components.values()], True)

  @property
  def new_average(self):
    if self.is_ts:
      assert(len(self) == 1)
      comp = self.components.values()[0]
      return comp.get_average()
    else:
      return get_average([comp.get_median(strip_first=True) for comp in self.components.values()])

class BuildAnalyser(object):
  def parse_data(self, data, template):
    result = template.copy()
    result['graph_result'] = data.old_average
    result['new_result'] = data.new_average
    return [result]

  def get_headers(self):
    return ['graph_result', 'new_result']

class ComponentAnalyser(object):
  """ Returns a result for each component of a test """

  def __init__(self):
    self.max_tests = -1

  def parse_data(self, data, template):
    results = []
    for name, comp in data.components.items():
      result = template.copy()
      result['test_name'] = name
      for num, run in enumerate(comp.values):
        result["test_%d" % num] = run
      self.max_tests = max(self.max_tests, len(comp))
      result['max'] = comp.max
      result['min'] = comp.min
      result['graph_median'] = comp.get_median(strip_max=True)
      result['new_median'] = comp.get_median(strip_first=True)
      result['test_runs'] = num + 1
      results.append(result)
    return results

  def get_headers(self):
    headers = ['test_name', 'test_runs', 'max', 'min', 'graph_median', 'new_median']
    for i in range(self.max_tests+1):
      headers.append('test_%d' % i)
    return headers
