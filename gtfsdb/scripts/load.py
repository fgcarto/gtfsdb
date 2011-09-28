import argparse
import pkg_resources
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import time

from gtfsdb import (
    Agency,
    Calendar,
    CalendarDate,
    FareAttribute,
    FareRule,
    FeedInfo,
    Frequency,
    model,
    Pattern,
    Route,
    RouteType,
    Shape,
    Stop,
    StopTime,
    Transfer,
    Trip,
    UniversalCalendar,
)
from gtfsdb.util import unzip_gtfs


def init_parser():
    parser = argparse.ArgumentParser(
        prog='gtfsdb-load',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        'file',
        help='URL or local directory path to GTFS zip FILE',
    )
    parser.add_argument(
        '--database_url',
        default='sqlite://',
        help='DATABASE URL with appropriate privileges'
    )
    parser.add_argument(
        '--is_geospatial',
        action='store_true',
        default=False,
        help='Database IS GEOSPATIAL',
    )
    parser.add_argument(
        '--schema',
        default=None,
        help='Database SCHEMA name',
    )
    args = parser.parse_args()
    return args


def main():


    # process command line args
    args = init_parser()
    for cls in model.DeclarativeBase.__subclasses__():
        cls.set_schema(args.schema)
        if args.is_geospatial and hasattr(cls, 'add_geometry_column'):
            cls.add_geometry_column()
    engine = create_engine(args.database_url)

    model.DeclarativeBase.metadata.drop_all(bind=engine)
    model.DeclarativeBase.metadata.create_all(bind=engine)
    gtfs_directory = unzip_gtfs(args.file)
    data_directory = pkg_resources.resource_filename('gtfsdb', 'data')

    # load lookup tables first
    RouteType.load(engine, data_directory, False)

    # load GTFS data files & transform/derive additional data
    # due to foreign key constraints these files need to be loaded in the appropriate order
    FeedInfo.load(engine, gtfs_directory)
    Agency.load(engine, gtfs_directory)
    Calendar.load(engine, gtfs_directory)
    CalendarDate.load(engine, gtfs_directory)
    Route.load(engine, gtfs_directory)
    Stop.load(engine, gtfs_directory)
    Transfer.load(engine, gtfs_directory)
    Shape.load(engine, gtfs_directory)
    Pattern.load(engine)
    Trip.load(engine, gtfs_directory)
    StopTime.load(engine, gtfs_directory)
    Frequency.load(engine, gtfs_directory)
    FareAttribute.load(engine, gtfs_directory)
    FareRule.load(engine, gtfs_directory)
    shutil.rmtree(gtfs_directory)
    UniversalCalendar.load(engine)

    # load derived geometries
    # currently only written for postgresql
    dialect_name = engine.url.get_dialect().name
    if args.is_geospatial and dialect_name == 'postgresql':
        s = ' - %s geom' %(Route.__tablename__)
        sys.stdout.write(s)
        start_seconds = time.time()
        Session = sessionmaker(bind=engine)
        session = Session()
        q = session.query(Route)
        for route in q:
            route.load_geometry(session)
            session.merge(route)
        session.commit()
        session.close()
        process_time = time.time() - start_seconds
        print ' (%.0f seconds)' %(process_time)


if __name__ == '__main__':
    start_seconds = time.time()
    start_time = time.localtime()
    print time.strftime('begin time: %H:%M:%S', start_time)
    main()
    end_time = time.localtime()
    print time.strftime('end time: %H:%M:%S', end_time)
    process_time = time.time() - start_seconds
    print 'processing time: %.0f seconds' %(process_time)
