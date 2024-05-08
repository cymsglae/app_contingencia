reference = {
    "journal": {
        "values": {
            "settings": {
                "appGeocoders": [
                    {
                        "singleLineFieldName": "SingleLine",
                        "name": "Esri World Geocoder",
                        "url": "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer",
                    },
                    {
                        "singleLineFieldName": "SingleLine",
                        "name": "san",
                        "placeholder": "",
                        "url": "https://sampleserver5.arcgisonline.com/arcgis/rest/services/Locators/SanDiego/GeocodeServer",
                    },
                ],
                "layout": {"id": "side"},
            },
            "title": "title",
            "story": {"storage": "WEBAPP", "sections": []},
            "template": {
                "name": "Map Journal",
                "createdWith": "1.14.1",
                "editedWith": "1.14.1",
            },
        }
    }
}

storymap_2 = {
    "root": "n-4xkUEe",
    "nodes": {
        "n-4xkUEe": {
            "type": "story",
            "data": {"storyTheme": "r-vlc4Kp"},
            "config": {"coverDate": "first-published"},
            "children": ["n-aTn8ak", "n-1AItUD", "n-cOeTah"],
        },
        "n-aTn8ak": {
            "type": "storycover",
            "data": {
                "type": "minimal",
                "title": "",
                "summary": "",
                "byline": "",
                "titlePanelPosition": "start",
            },
        },
        "n-1AItUD": {
            "type": "navigation",
            "data": {"links": []},
            "config": {"isHidden": True},
        },
        "n-cOeTah": {"type": "credits"},
    },
    "resources": {
        "r-vlc4Kp": {
            "type": "story-theme",
            "data": {"themeId": "summit", "themeBaseVariableOverrides": {}},
        }
    },
}

briefing = {
    "root": "n-k23c2p",
    "nodes": {
        "n-XK0GeP": {"type": "briefing-ui", "children": ["n-11SuEF"]},
        "n-11SuEF": {
            "type": "briefing-slide",
            "data": {"layout": "cover"},
            "children": ["n-3r3mhh"],
        },
        "n-3r3mhh": {
            "type": "storycover",
            "data": {
                "type": "sidebyside",
                "title": "",
                "summary": "",
                "byline": "",
                "titlePanelPosition": "start",
            },
            "children": [],
        },
        "n-k23c2p": {
            "type": "briefing",
            "data": {"storyTheme": "r-vlc4Kp"},
            "children": ["n-XK0GeP"],
        },
    },
    "resources": {
        "r-vlc4Kp": {
            "type": "story-theme",
            "data": {"themeId": "summit", "themeBaseVariableOverrides": {}},
        }
    },
}

collection = {
    "root": "n-vCW523",
    "nodes": {
        "n-vCW523": {
            "type": "collection",
            "data": {"storyTheme": "r-QvId58"},
            "children": ["n-eERiZz"],
        },
        "n-eERiZz": {
            "type": "collection-ui",
            "data": {"items": []},
            "children": ["n-U3Ou63", "n-JTJJo2"],
        },
        "n-U3Ou63": {
            "type": "collection-cover",
            "data": {"title": "", "summary": "", "byline": "", "type": "tiles"},
        },
        "n-JTJJo2": {"type": "collection-nav", "data": {"type": "compact"}},
    },
    "resources": {
        "r-QvId58": {
            "type": "story-theme",
            "data": {"themeId": "summit", "themeBaseVariableOverrides": {}},
        }
    },
}
