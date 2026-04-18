"""GraphQL query strings for the Tibber API.

All inputs that originate outside this module (home ids, cursors, date
filters, notification title/message) are passed as GraphQL variables to
prevent string-based injection.  Field names that vary by call
(``consumption`` vs ``production``) are internal constants and are
embedded via Python formatting at import/call time.
"""

from __future__ import annotations

INFO = """
{
  viewer {
    name
    userId
    websocketSubscriptionUrl
    homes {
      id
      appNickname
      features { realTimeConsumptionEnabled }
      currentSubscription { status }
    }
  }
}
"""

# Static home metadata — changes rarely; fetched once per day.
UPDATE_HOME_INFO = """
query($homeId: ID!) {
  viewer {
    home(id: $homeId) {
      appNickname
      timeZone
      address {
        address1 address2 address3 postalCode city country latitude longitude
      }
      meteringPointData {
        consumptionEan gridCompany gridAreaCode priceAreaCode
        productionEan energyTaxType vatType estimatedAnnualConsumption
      }
      owner {
        firstName isCompany name middleName lastName
        organizationNo language
        contactInfo { email mobile }
      }
      subscriptions { validFrom validTo status }
      features { realTimeConsumptionEnabled }
    }
  }
}
"""

# Dynamic price info — fetched on every price refresh cycle.
UPDATE_PRICE_INFO = """
query($homeId: ID!) {
  viewer {
    home(id: $homeId) {
      currentSubscription {
        priceInfo(resolution: QUARTER_HOURLY) {
          current  { total energy tax startsAt currency level }
          today    { total energy tax startsAt currency level }
          tomorrow { total energy tax startsAt currency level }
        }
      }
    }
  }
}
"""

UPDATE_CURRENT_PRICE = """
query($homeId: ID!) {
  viewer {
    home(id: $homeId) {
      currentSubscription {
        priceInfo(resolution: QUARTER_HOURLY) {
          current { total energy tax startsAt currency }
        }
      }
    }
  }
}
"""

# Historic data template — ``direction`` and ``resolution`` are internal
# constants; they are embedded via ``str.format`` at call time.  External
# values (homeId, batch size, cursor) flow through GraphQL variables.
_HISTORIC_DATA_TMPL = """
query($homeId: ID!, $n: Int!, $before: String) {{
  viewer {{
    home(id: $homeId) {{
      {direction}(resolution: {resolution}, last: $n, before: $before) {{
        pageInfo {{ hasPreviousPage startCursor }}
        nodes {{ from unitPrice unitPriceVAT {direction} cost currency }}
      }}
    }}
  }}
}}
"""

_HISTORIC_DATA_DATE_TMPL = """
query($homeId: ID!, $n: Int!, $filterFrom: String) {{
  viewer {{
    home(id: $homeId) {{
      {direction}(resolution: {resolution}, last: $n, filterFrom: $filterFrom) {{
        nodes {{ from to unitPrice unitPriceVAT {direction} cost currency }}
      }}
    }}
  }}
}}
"""


def historic_data_query(direction: str, resolution: str) -> str:
    """Return the paginated historic-data query for a given direction."""
    return _HISTORIC_DATA_TMPL.format(direction=direction, resolution=resolution)


def historic_data_date_query(direction: str, resolution: str) -> str:
    """Return the date-filtered historic-data query for a given direction."""
    return _HISTORIC_DATA_DATE_TMPL.format(direction=direction, resolution=resolution)


HISTORIC_PRICE = """
query($homeId: ID!) {
  viewer {
    home(id: $homeId) {
      currentSubscription {
        priceRating {
          hourly { entries { time total } }
        }
      }
    }
  }
}
"""

LIVE_SUBSCRIBE = """
subscription($homeId: ID!) {
  liveMeasurement(homeId: $homeId) {
    timestamp
    power powerProduction
    accumulatedConsumption accumulatedProduction
    accumulatedConsumptionLastHour accumulatedProductionLastHour
    accumulatedCost accumulatedReward currency
    minPower averagePower maxPower
    minPowerProduction maxPowerProduction
    lastMeterConsumption lastMeterProduction
    voltagePhase1 voltagePhase2 voltagePhase3
    currentL1 currentL2 currentL3
    signalStrength powerFactor
    powerReactive powerProductionReactive
  }
}
"""

PUSH_NOTIFICATION = """
mutation($title: String!, $message: String!) {
  sendPushNotification(input: {
    title: $title
    message: $message
    screenToOpen: HOME
  }) {
    successful
    pushedToNumberOfDevices
  }
}
"""
