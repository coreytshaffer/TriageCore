import json
def processData(d):
  # parses data
  try:
    j = json.loads(d)
    return j['value'] * 2
  except:
    return None

def main():
    print(processData('{"value": 21}'))

if __name__ == "__main__":
    main()
