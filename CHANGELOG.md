# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2025-07-30

### Added

- **Update Checker**: Automatic GitHub release version checking on startup
  - Configurable update notifications via `update_checks` setting in unshackle.yaml
  - Non-blocking HTTP requests with 5-second timeout for performance
  - Smart semantic version comparison supporting all version formats (x.y.z, x.y, x)
  - Graceful error handling for network issues and API failures
  - User-friendly update notifications with current → latest version display
  - Direct links to GitHub releases page for easy updates
- **HDR10+ Support**: Enhanced HDR10+ metadata processing for hybrid tracks
  - HDR10+ tool binary support (`hdr10plus_tool`) added to binaries module
  - HDR10+ to Dolby Vision conversion capabilities in hybrid processing
  - Enhanced metadata extraction for HDR10+ content
- **Duration Fix Handling**: Added duration correction for video and hybrid tracks
- **Temporary Directory Management**: Automatic creation of temp directories for attachment downloads

### Changed

- Enhanced configuration system with new `update_checks` boolean option (defaults to true)
- Updated sample unshackle.yaml with update checker configuration documentation
- Improved console styling consistency using `bright_black` for dimmed text
- **Environment Dependency Check**: Complete overhaul with detailed categorization and status summary
  - Organized dependencies by category (Core, HDR, Download, Subtitle, Player, Network)
  - Enhanced status reporting with compact summary display
  - Improved tool requirement tracking and missing dependency alerts
- **Hybrid Track Processing**: Significant improvements to HDR10+ and Dolby Vision handling
  - Enhanced metadata extraction and processing workflows
  - Better integration with HDR processing tools

### Removed

- **Docker Workflow**: Removed Docker build and publish GitHub Actions workflow for manual builds

## [1.1.0] - 2025-07-29

### Added

- **HDR10+DV Hybrid Processing**: New `-r HYBRID` command for processing HDR10 and Dolby Vision tracks
  - Support for hybrid HDR processing and injection using dovi_tool
  - New hybrid track processing module for seamless HDR10/DV conversion
  - Automatic detection and handling of HDR10 and DV metadata
- Support for HDR10 and DV tracks in hybrid mode for EXAMPLE service
- Binary availability check for dovi_tool in hybrid mode operations
- Enhanced track processing capabilities for HDR content

### Fixed

- Import order issues and missing json import in hybrid processing
- UV installation process and error handling improvements
- Binary search functionality updated to use `binaries.find`

### Changed

- Updated package version from 1.0.2 to 1.1.0
- Enhanced dl.py command processing for hybrid mode support
- Improved core titles (episode/movie) processing for HDR content
- Extended tracks module with hybrid processing capabilities
