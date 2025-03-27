# Changelog

## [Unreleased]

### Fixed
- Fixed Jenkins CSRF protection handling to properly manage sessions and crumbs
- Added automatic crumb refresh when authentication fails due to an expired crumb
- Improved error handling and reporting for Jenkins API requests
- Updated tests to properly verify CSRF protection functionality

### Added
- Added reference implementation in `scripts/jenkins_api_fix.py` demonstrating proper Jenkins API communication
- Added detailed documentation on Jenkins CSRF protection in `scripts/README.md`
